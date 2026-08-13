"""Integration tests for auth flow against real PostgreSQL.

Requires Postgres up (docker compose). The user is created via the repository
in the conftest fixture, exactly as the seed script does.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture()
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_login_success(client, admin_user) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user["email"], "password": admin_user["password"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(client, admin_user) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user["email"], "password": "wrong"},
    )
    assert r.status_code == 401


async def test_me_requires_token(client) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_with_token(client, admin_user) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user["email"], "password": admin_user["password"]},
    )
    token = login.json()["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == admin_user["email"]
    assert r.json()["role"] == "admin"


async def test_refresh_flow(client, admin_user) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user["email"], "password": admin_user["password"]},
    )
    refresh_token = login.json()["refresh_token"]
    r = await client.post("/api/v1/auth/refresh", params={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_documents_requires_auth(client) -> None:
    r = await client.get("/api/v1/documents")
    assert r.status_code == 401
