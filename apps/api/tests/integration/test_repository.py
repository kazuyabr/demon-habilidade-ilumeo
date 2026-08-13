"""Integration tests for repository persistence + cascade delete."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from risklens.infrastructure.db import models as m
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.db.session import SessionFactory

pytestmark = pytest.mark.integration


async def _count(table) -> int:
    async with SessionFactory() as session:
        result = await session.execute(select(func.count()).select_from(table))
        return int(result.scalar_one())


async def test_document_cascade_delete(admin_user) -> None:
    doc = await repo.create_document(
        filename="r.md",
        title="Relatório",
        storage_path="ab/abc.md",
        content_type="md",
        sha256=uuid4().hex,
        size_bytes=10,
        created_by=admin_user["id"],
    )
    await repo.create_extraction(doc.id, schema_name="credit_report")
    await repo.update_extraction_result(
        (await repo.get_extraction_by_document(doc.id)).id,
        status="completed",
        data={"company_name": "X"},
        confidence=0.9,
    )
    assert await _count(m.Document) >= 1

    await repo.delete_document(doc.id)

    assert await repo.get_document_by_id(doc.id) is None
    assert await repo.get_extraction_by_document(doc.id) is None


async def test_agent_run_lifecycle(admin_user) -> None:
    run = await repo.create_agent_run("Qual o risco?", created_by=admin_user["id"], model_used="fake")
    await repo.append_agent_step(run.id, {"kind": "plan", "output": "x"})
    await repo.finish_agent_run(run.id, status="completed", result={"risk_score": 50})

    loaded = await repo.get_agent_run(run.id)
    assert loaded is not None
    assert loaded.status == "completed"
    assert loaded.result == {"risk_score": 50}
    assert len(loaded.trace) == 1


async def test_duplicate_sha_rejected(admin_user) -> None:
    sha = uuid4().hex
    await repo.create_document(
        filename="a.md", title="A", storage_path="a/a.md", content_type="md",
        sha256=sha, size_bytes=1, created_by=admin_user["id"],
    )
    # unique index on sha256 rejects the duplicate at commit time
    with pytest.raises(Exception) as exc:
        await repo.create_document(
            filename="b.md", title="B", storage_path="b/b.md", content_type="md",
            sha256=sha, size_bytes=1, created_by=admin_user["id"],
        )
    assert "sha256" in str(exc.value) or "duplicate" in str(exc.value).lower()
