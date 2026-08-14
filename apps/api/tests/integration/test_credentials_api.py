"""Integration tests for BYOK per-user credentials."""

from __future__ import annotations

import httpx
import pytest

from risklens.application.services import credential_service

pytestmark = pytest.mark.integration


@pytest.fixture()
async def client(app, admin_user):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        login = await c.post(
            "/api/v1/auth/login",
            data={"username": admin_user["email"], "password": admin_user["password"]},
        )
        c.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield c


async def test_credentials_crud_and_byok_resolution(client, admin_user) -> None:
    r = await client.put(
        "/api/v1/auth/credentials/opencode-go",
        json={"api_key": "sk-test-1234", "base_url": "http://localhost:9999/v1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["has_api_key"] is True
    assert body["api_key_last4"] == "1234"
    assert body["has_base_url"] is True

    g = await client.get("/api/v1/auth/credentials")
    assert g.status_code == 200
    items = {i["provider"]: i for i in g.json()}
    assert items["opencode-go"]["api_key_last4"] == "1234"

    # resolution: user credential overrides the env default
    base, key = await credential_service.get_effective_chat_endpoint(admin_user["id"], "opencode-go")
    assert key == "sk-test-1234"
    assert base == "http://localhost:9999/v1"

    d = await client.delete("/api/v1/auth/credentials/opencode-go")
    assert d.status_code == 204
    g2 = await client.get("/api/v1/auth/credentials")
    assert "opencode-go" not in {i["provider"] for i in g2.json()}


async def test_credential_unknown_provider(client) -> None:
    r = await client.put("/api/v1/auth/credentials/nao-existe", json={"api_key": "x"})
    assert r.status_code == 404


async def test_credential_requires_field(client) -> None:
    r = await client.put("/api/v1/auth/credentials/lmstudio", json={})
    assert r.status_code == 400
