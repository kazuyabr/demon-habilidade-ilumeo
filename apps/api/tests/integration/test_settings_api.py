"""Integration tests for the settings panel API (runtime AI config)."""

from __future__ import annotations

import httpx
import pytest

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


async def test_get_settings(client) -> None:
    r = await client.get("/api/v1/admin/settings")
    assert r.status_code == 200
    body = r.json()
    assert "chat_provider" in body["config"]
    assert body["overridden"] == []


async def test_update_and_reset_settings(client) -> None:
    r = await client.put("/api/v1/admin/settings", json={"temperature": 0.5})
    assert r.status_code == 200
    body = r.json()
    assert body["config"]["temperature"] == 0.5
    assert "temperature" in body["overridden"]

    # reset back to env default
    r2 = await client.put("/api/v1/admin/settings", json={"temperature": None})
    assert r2.status_code == 200
    assert "temperature" not in r2.json()["overridden"]


async def test_update_invalid_provider_model(client) -> None:
    r = await client.put(
        "/api/v1/admin/settings",
        json={"chat_provider": "fastembed", "chat_model": "x"},  # fastembed has no chat
    )
    assert r.status_code == 400


async def test_test_connection_returns_shape(client) -> None:
    # Provider may not be reachable in CI — the endpoint still returns ok:bool
    r = await client.post(
        "/api/v1/admin/settings/test",
        json={"provider": "lmstudio", "model": "google/gemma-3-4b"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] in (True, False)
    assert body["model"] == "google/gemma-3-4b"
