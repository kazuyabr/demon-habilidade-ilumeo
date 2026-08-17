"""Integration tests for eval definitions CRUD, validation and run creation."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from risklens.core.security import hash_password
from risklens.infrastructure.db import repository as repo

pytestmark = pytest.mark.integration


@pytest.fixture()
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client, email: str, password: str) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


async def _make_user(role: str) -> dict:
    email = f"{role}-{uuid4().hex[:8]}@risklens.test"
    user = await repo.create_user(
        email=email,
        full_name=role.title(),
        hashed_password=hash_password("Secret@123"),
        role=role,
    )
    return {"id": user.id, "email": email, "password": "Secret@123", "role": role}


def _case() -> dict:
    return {
        "document_file": "caso.md",
        "document_text": "Empresa ABC: risco baixo, receita estável, sem red flags.",
        "expected": {
            "company_name": "Empresa ABC",
            "sector": "serviços",
            "analysis_date": "10/08/2026",
            "overall_risk_score": 30,
            "risk_rating": "A",
            "decision": "approve",
            "decision_justification": "Sem sinais de risco.",
            "confidence": 0.9,
            "red_flags": [],
        },
    }


async def test_definition_crud_flow(client, admin_user) -> None:
    token = await _login(client, admin_user["email"], admin_user["password"])
    headers = {"Authorization": f"Bearer {token}"}
    slug = f"eval-{uuid4().hex[:8]}"

    created = await client.post(
        "/api/v1/evals/definitions",
        headers=headers,
        json={
            "slug": slug,
            "title": "Teste eval",
            "schema_name": "credit_report",
            "cases": [_case()],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["n_cases"] == 1
    assert body["slug"] == slug
    definition_id = body["id"]

    listed = await client.get("/api/v1/evals/definitions", headers=headers)
    assert listed.status_code == 200
    assert any(d["slug"] == slug for d in listed.json())

    detail = await client.get(f"/api/v1/evals/definitions/{definition_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["cases"][0]["document_file"] == "caso.md"

    updated = await client.patch(
        f"/api/v1/evals/definitions/{definition_id}",
        headers=headers,
        json={"title": "Teste eval editado"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Teste eval editado"

    deleted = await client.delete(f"/api/v1/evals/definitions/{definition_id}", headers=headers)
    assert deleted.status_code == 204
    gone = await client.get(f"/api/v1/evals/definitions/{definition_id}", headers=headers)
    assert gone.status_code == 404


async def test_duplicate_slug_rejected(client, admin_user) -> None:
    token = await _login(client, admin_user["email"], admin_user["password"])
    headers = {"Authorization": f"Bearer {token}"}
    slug = f"dup-{uuid4().hex[:8]}"
    payload = {"slug": slug, "title": "Dup", "cases": [_case()]}
    assert (await client.post("/api/v1/evals/definitions", headers=headers, json=payload)).status_code == 201
    assert (await client.post("/api/v1/evals/definitions", headers=headers, json=payload)).status_code == 409


async def test_definition_requires_admin(client, admin_user) -> None:
    analyst = await _make_user("analyst")
    token = await _login(client, analyst["email"], analyst["password"])
    r = await client.post(
        "/api/v1/evals/definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={"slug": f"nao-{uuid4().hex[:8]}", "title": "X", "cases": [_case()]},
    )
    assert r.status_code == 403


async def test_validate_endpoint(client, admin_user) -> None:
    token = await _login(client, admin_user["email"], admin_user["password"])
    headers = {"Authorization": f"Bearer {token}"}
    ok = await client.post(
        "/api/v1/evals/definitions/validate",
        headers=headers,
        json={"schema_name": "credit_report", "expected": _case()["expected"]},
    )
    assert ok.status_code == 200
    assert ok.json()["valid"] is True

    bad = await client.post(
        "/api/v1/evals/definitions/validate",
        headers=headers,
        json={"schema_name": "credit_report", "expected": {"company_name": 123}},
    )
    assert bad.status_code == 200
    assert bad.json()["valid"] is False
    assert bad.json()["errors"]


async def test_delete_guard_with_running_run(client, admin_user) -> None:
    token = await _login(client, admin_user["email"], admin_user["password"])
    headers = {"Authorization": f"Bearer {token}"}
    slug = f"guard-{uuid4().hex[:8]}"
    created = await client.post(
        "/api/v1/evals/definitions",
        headers=headers,
        json={"slug": slug, "title": "Guard", "cases": [_case()]},
    )
    definition_id = created.json()["id"]

    run = await repo.create_eval_run(slug, model_used="fake/model", definition_id=definition_id)
    try:
        denied = await client.delete(f"/api/v1/evals/definitions/{definition_id}", headers=headers)
        assert denied.status_code == 409
    finally:
        await repo.finish_eval_run(run.id, status="completed", metrics={"n_cases": 1})

    allowed = await client.delete(f"/api/v1/evals/definitions/{definition_id}", headers=headers)
    assert allowed.status_code == 204
