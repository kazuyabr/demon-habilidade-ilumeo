"""Shared pytest fixtures.

Unit tests never touch infrastructure. Integration tests rely on the
Postgres/Redis started by docker-compose (see CI workflow `api-integration`).
"""

from __future__ import annotations

import os
import uuid

# Must be set before importing risklens modules: test mode uses NullPool so
# the async engine never carries connections across pytest event loops.
os.environ["APP_ENV"] = "test"

import pytest  # noqa: E402

from risklens.core.security import hash_password  # noqa: E402
from risklens.infrastructure.db import repository as repo  # noqa: E402


@pytest.fixture()
async def admin_user() -> dict:
    email = f"admin-{uuid.uuid4().hex[:8]}@risklens.test"
    user = await repo.create_user(
        email=email,
        full_name="Test Admin",
        hashed_password=hash_password("Secret@123"),
        role="admin",
    )
    yield {"id": user.id, "email": email, "password": "Secret@123", "role": "admin"}
    # cleanup: documents cascade to chunks/extractions; then the user can be dropped
    from risklens.infrastructure.db.session import SessionFactory
    from sqlalchemy import text

    async with SessionFactory() as session:
        await session.execute(text("DELETE FROM documents WHERE created_by = :uid"), {"uid": user.id})
        await session.execute(text("DELETE FROM agent_runs WHERE created_by = :uid"), {"uid": user.id})
        await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user.id})
        await session.commit()


@pytest.fixture()
def app():
    from risklens.main import app

    return app
