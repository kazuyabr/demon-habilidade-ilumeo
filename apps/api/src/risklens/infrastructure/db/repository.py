"""Persistence functions for domain aggregates.

Session-per-operation (opens its own async session via SessionFactory) so the
same code works from HTTP request scope and from the arq worker. Fine for
this workload; a unit-of-work pattern would be the scale-up (see docs).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from risklens.infrastructure.db import models as m
from risklens.infrastructure.db.session import SessionFactory

# --- users ---


async def get_user_by_email(email: str) -> m.User | None:
    async with SessionFactory() as session:
        result = await session.execute(select(m.User).where(m.User.email == email.lower()))
        return result.scalar_one_or_none()


async def get_user_by_id(user_id: UUID) -> m.User | None:
    async with SessionFactory() as session:
        return await session.get(m.User, user_id)


async def create_user(*, email: str, full_name: str, hashed_password: str, role: str) -> m.User:
    async with SessionFactory() as session:
        user = m.User(email=email.lower(), full_name=full_name, hashed_password=hashed_password, role=role)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# --- documents ---


async def create_document(
    *,
    filename: str,
    title: str,
    storage_path: str,
    content_type: str,
    sha256: str,
    size_bytes: int,
    created_by: UUID | None,
    source: str | None = None,
) -> m.Document:
    async with SessionFactory() as session:
        doc = m.Document(
            filename=filename,
            title=title,
            storage_path=storage_path,
            content_type=content_type,
            sha256=sha256,
            size_bytes=size_bytes,
            created_by=created_by,
            source=source,
            status="pending",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        return doc


async def get_document_by_id(document_id: UUID) -> m.Document | None:
    async with SessionFactory() as session:
        return await session.get(m.Document, document_id)


async def get_document_by_sha256(sha256: str) -> m.Document | None:
    async with SessionFactory() as session:
        result = await session.execute(select(m.Document).where(m.Document.sha256 == sha256))
        return result.scalar_one_or_none()


async def list_documents(limit: int = 50, offset: int = 0) -> list[m.Document]:
    async with SessionFactory() as session:
        result = await session.execute(
            select(m.Document).order_by(m.Document.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())


async def update_document_status(document_id: UUID, *, status: str, error_message: str | None = None) -> None:
    async with SessionFactory() as session:
        doc = await session.get(m.Document, document_id)
        if doc is None:
            return
        doc.status = status
        if error_message is not None:
            doc.error_message = error_message
        await session.commit()


async def delete_document(document_id: UUID) -> None:
    async with SessionFactory() as session:
        doc = await session.get(m.Document, document_id)
        if doc:
            await session.delete(doc)
            await session.commit()


# --- extractions ---


async def create_extraction(
    document_id: UUID,
    *,
    schema_name: str,
    status: str = "processing",
) -> m.Extraction:
    async with SessionFactory() as session:
        ext = m.Extraction(document_id=document_id, schema_name=schema_name, status=status)
        session.add(ext)
        await session.commit()
        await session.refresh(ext)
        return ext


async def get_extraction_by_document(document_id: UUID) -> m.Extraction | None:
    async with SessionFactory() as session:
        result = await session.execute(select(m.Extraction).where(m.Extraction.document_id == document_id))
        return result.scalar_one_or_none()


async def update_extraction_result(
    extraction_id: UUID,
    *,
    status: str,
    data: dict | None = None,
    raw_llm_output: str | None = None,
    model_used: str | None = None,
    confidence: float | None = None,
    error_message: str | None = None,
) -> None:
    async with SessionFactory() as session:
        ext = await session.get(m.Extraction, extraction_id)
        if ext is None:
            return
        ext.status = status
        if data is not None:
            ext.data = data
        if raw_llm_output is not None:
            ext.raw_llm_output = raw_llm_output
        if model_used is not None:
            ext.model_used = model_used
        if confidence is not None:
            ext.confidence = confidence
        if error_message is not None:
            ext.error_message = error_message
        await session.commit()


# --- agent runs ---


async def create_agent_run(question: str, created_by: UUID | None, model_used: str) -> m.AgentRun:
    async with SessionFactory() as session:
        run = m.AgentRun(question=question, created_by=created_by, model_used=model_used, status="running")
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


async def get_agent_run(run_id: UUID) -> m.AgentRun | None:
    async with SessionFactory() as session:
        return await session.get(m.AgentRun, run_id)


async def list_agent_runs(limit: int = 20) -> list[m.AgentRun]:
    async with SessionFactory() as session:
        result = await session.execute(select(m.AgentRun).order_by(m.AgentRun.created_at.desc()).limit(limit))
        return list(result.scalars().all())


async def append_agent_step(run_id: UUID, step: dict) -> None:
    async with SessionFactory() as session:
        run = await session.get(m.AgentRun, run_id)
        if run is None:
            return
        trace = list(run.trace or [])
        trace.append(step)
        run.trace = trace
        await session.commit()


async def finish_agent_run(
    run_id: UUID,
    *,
    status: str,
    result: dict | None = None,
    error_message: str | None = None,
) -> None:
    async with SessionFactory() as session:
        run = await session.get(m.AgentRun, run_id)
        if run is None:
            return
        run.status = status
        if result is not None:
            run.result = result
        if error_message is not None:
            run.error_message = error_message
        await session.commit()


# --- eval runs ---


async def create_eval_run(name: str, model_used: str, definition_id: UUID | None = None) -> m.EvalRun:
    async with SessionFactory() as session:
        run = m.EvalRun(name=name, model_used=model_used, status="running", definition_id=definition_id)
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


async def get_eval_run(run_id: UUID) -> m.EvalRun | None:
    async with SessionFactory() as session:
        return await session.get(m.EvalRun, run_id)


async def list_eval_runs(limit: int = 20) -> list[m.EvalRun]:
    async with SessionFactory() as session:
        result = await session.execute(select(m.EvalRun).order_by(m.EvalRun.created_at.desc()).limit(limit))
        return list(result.scalars().all())


async def finish_eval_run(
    run_id: UUID,
    *,
    status: str,
    metrics: dict | None = None,
    items: list | None = None,
    error_message: str | None = None,
) -> None:
    async with SessionFactory() as session:
        run = await session.get(m.EvalRun, run_id)
        if run is None:
            return
        run.status = status
        if metrics is not None:
            run.metrics = metrics
        if items is not None:
            run.items = items
        if error_message is not None:
            run.error_message = error_message
        await session.commit()


async def has_running_eval_run(definition_id: UUID) -> bool:
    """True if the definition has any run still in progress (delete guard)."""
    async with SessionFactory() as session:
        result = await session.execute(
            select(m.EvalRun.id).where(m.EvalRun.definition_id == definition_id, m.EvalRun.status == "running").limit(1)
        )
        return result.scalar_one_or_none() is not None


# --- eval definitions ---


async def list_eval_definitions(limit: int = 100) -> list[m.EvalDefinition]:
    async with SessionFactory() as session:
        result = await session.execute(
            select(m.EvalDefinition).order_by(m.EvalDefinition.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


async def get_eval_definition_by_id(definition_id: UUID) -> m.EvalDefinition | None:
    async with SessionFactory() as session:
        return await session.get(m.EvalDefinition, definition_id)


async def get_eval_definition_by_slug(slug: str) -> m.EvalDefinition | None:
    async with SessionFactory() as session:
        result = await session.execute(select(m.EvalDefinition).where(m.EvalDefinition.slug == slug).limit(1))
        return result.scalar_one_or_none()


async def create_eval_definition(
    *,
    slug: str,
    title: str,
    schema_name: str,
    cases: list,
    description: str | None = None,
    thresholds: dict | None = None,
    created_by: UUID | None = None,
) -> m.EvalDefinition:
    async with SessionFactory() as session:
        definition = m.EvalDefinition(
            slug=slug,
            title=title,
            description=description,
            schema_name=schema_name,
            cases=cases,
            thresholds=thresholds,
            created_by=created_by,
        )
        session.add(definition)
        await session.commit()
        await session.refresh(definition)
        return definition


async def update_eval_definition(definition_id: UUID, **fields) -> m.EvalDefinition | None:
    async with SessionFactory() as session:
        definition = await session.get(m.EvalDefinition, definition_id)
        if definition is None:
            return None
        for key, value in fields.items():
            setattr(definition, key, value)
        await session.commit()
        await session.refresh(definition)
        return definition


async def delete_eval_definition(definition_id: UUID) -> None:
    async with SessionFactory() as session:
        definition = await session.get(m.EvalDefinition, definition_id)
        if definition is not None:
            await session.delete(definition)
            await session.commit()
