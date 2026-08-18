"""Eval routes: definitions (client-managed golden sets) + runs + results."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from risklens.api.deps import get_current_user, get_job_queue, require_roles
from risklens.api.schemas import (
    EvalDefinitionCreate,
    EvalDefinitionDetail,
    EvalDefinitionOut,
    EvalDefinitionUpdate,
    EvalRunBatchCreate,
    EvalRunCreate,
    EvalRunOut,
    EvalValidateIn,
    EvalValidateOut,
)
from risklens.domain.schemas import SCHEMA_REGISTRY
from risklens.infrastructure.ai import registry, runtime
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.db.models import User

router = APIRouter(prefix="/evals", tags=["evals"])

_KNOWN_METRICS = {
    "field_exact_accuracy",
    "field_fuzzy_similarity",
    "decision_accuracy",
    "redflag_recall",
    "score_mae",
    "llm_judge_score",
}


def _definition_out(definition) -> EvalDefinitionOut:
    return EvalDefinitionOut(
        id=definition.id,
        slug=definition.slug,
        title=definition.title,
        description=definition.description,
        schema_name=definition.schema_name,
        n_cases=len(definition.cases),
        thresholds=definition.thresholds,
        created_at=definition.created_at,
        updated_at=definition.updated_at,
    )


def _detail_out(definition) -> EvalDefinitionDetail:
    return EvalDefinitionDetail(
        **_definition_out(definition).model_dump(),
        cases=definition.cases,
    )


def _validate_thresholds(thresholds: dict | None) -> None:
    if not thresholds:
        return
    unknown = set(thresholds) - _KNOWN_METRICS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"métricas desconhecidas no limiar: {', '.join(sorted(unknown))}",
        )


def _validate_schema(schema_name: str) -> None:
    if schema_name not in SCHEMA_REGISTRY:
        raise HTTPException(
            status_code=422,
            detail=f"schema desconhecido: {schema_name} (disponíveis: {', '.join(SCHEMA_REGISTRY)})",
        )


def _validate_cases(schema_name: str, cases: list) -> None:
    model_cls = SCHEMA_REGISTRY[schema_name]
    errors: list[str] = []
    for i, case in enumerate(cases):
        if not (case.document_text or "").strip():
            errors.append(f"caso {i + 1}: document_text vazio")
        try:
            model_cls.model_validate(case.expected)
        except Exception as exc:  # noqa: BLE001 - collect all case errors
            errors.append(f"caso {i + 1} (expected): {str(exc)[:200]}")
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))


@router.get("/definitions", response_model=list[EvalDefinitionOut])
async def list_definitions(
    _: User = Depends(get_current_user),
) -> list[EvalDefinitionOut]:
    definitions = await repo.list_eval_definitions()
    return [_definition_out(d) for d in definitions]


@router.get("/definitions/{definition_id}", response_model=EvalDefinitionDetail)
async def get_definition(
    definition_id: UUID,
    _: User = Depends(get_current_user),
) -> EvalDefinitionDetail:
    definition = await repo.get_eval_definition_by_id(definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="Definição de eval não encontrada")
    return _detail_out(definition)


@router.post("/definitions", response_model=EvalDefinitionDetail, status_code=201)
async def create_definition(
    body: EvalDefinitionCreate,
    user: User = Depends(require_roles("admin")),
) -> EvalDefinitionDetail:
    _validate_schema(body.schema_name)
    _validate_cases(body.schema_name, body.cases)
    _validate_thresholds(body.thresholds)
    existing = await repo.get_eval_definition_by_slug(body.slug)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Slug já existe: {body.slug}")
    definition = await repo.create_eval_definition(
        slug=body.slug,
        title=body.title,
        description=body.description,
        schema_name=body.schema_name,
        cases=[c.model_dump() for c in body.cases],
        thresholds=body.thresholds,
        created_by=user.id,
    )
    return _detail_out(definition)


@router.patch("/definitions/{definition_id}", response_model=EvalDefinitionDetail)
async def update_definition(
    definition_id: UUID,
    body: EvalDefinitionUpdate,
    _: User = Depends(require_roles("admin")),
) -> EvalDefinitionDetail:
    definition = await repo.get_eval_definition_by_id(definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="Definição de eval não encontrada")
    updates = body.model_dump(exclude_unset=True)
    schema_name = updates.get("schema_name", definition.schema_name)
    _validate_schema(schema_name)
    cases = updates.get("cases")
    if cases is not None:
        _validate_cases(schema_name, cases)
        updates["cases"] = [c.model_dump() for c in cases]
    _validate_thresholds(updates.get("thresholds"))
    updated = await repo.update_eval_definition(definition_id, **updates)
    return _detail_out(updated)


@router.delete("/definitions/{definition_id}", status_code=204)
async def delete_definition(
    definition_id: UUID,
    _: User = Depends(require_roles("admin")),
) -> None:
    definition = await repo.get_eval_definition_by_id(definition_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="Definição de eval não encontrada")
    if await repo.has_running_eval_run(definition_id):
        raise HTTPException(status_code=409, detail="Há uma execução em andamento desta definição")
    await repo.delete_eval_definition(definition_id)


@router.post("/definitions/validate", response_model=EvalValidateOut)
async def validate_expected(
    body: EvalValidateIn,
    _: User = Depends(require_roles("admin", "analyst")),
) -> EvalValidateOut:
    if body.schema_name not in SCHEMA_REGISTRY:
        return EvalValidateOut(valid=False, errors=[f"schema desconhecido: {body.schema_name}"])
    try:
        SCHEMA_REGISTRY[body.schema_name].model_validate(body.expected)
        return EvalValidateOut(valid=True)
    except Exception as exc:  # noqa: BLE001 - pydantic ValidationError to user-facing list
        return EvalValidateOut(valid=False, errors=[str(exc)[:500]])


@router.post("/runs", response_model=EvalRunOut)
async def create_eval(
    body: EvalRunCreate,
    user: User = Depends(require_roles("admin", "analyst")),
    queue=Depends(get_job_queue),
) -> EvalRunOut:
    if body.definition_id is not None:
        definition = await repo.get_eval_definition_by_id(body.definition_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Definição de eval não encontrada")
    elif body.name is not None:
        definition = await repo.get_eval_definition_by_slug(body.name)
        if definition is None:
            raise HTTPException(status_code=404, detail=f"Definição de eval não encontrada: {body.name}")
    else:
        raise HTTPException(status_code=422, detail="Informe definition_id ou name")

    cfg = runtime.get_cached_config()
    provider = (body.provider or str(cfg["chat_provider"])).lower()
    model = body.model or str(cfg["chat_model"])
    if body.provider or body.model:
        try:
            registry.require_chat_model(provider, model)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

    run = await repo.create_eval_run(
        definition.slug,
        model_used=f"{provider}/{model}",
        definition_id=definition.id,
    )
    await queue.enqueue(
        "run_eval_job",
        _job_id=str(run.id),
        run_id=str(run.id),
        definition_id=str(definition.id),
        provider=provider,
        model=model,
        user_id=str(user.id),
    )
    return EvalRunOut.model_validate(run)


async def _resolve_definition(definition_id: UUID | None, name: str | None):
    if definition_id is not None:
        definition = await repo.get_eval_definition_by_id(definition_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Definição de eval não encontrada")
    elif name is not None:
        definition = await repo.get_eval_definition_by_slug(name)
        if definition is None:
            raise HTTPException(status_code=404, detail=f"Definição de eval não encontrada: {name}")
    else:
        raise HTTPException(status_code=422, detail="Informe definition_id ou name")
    return definition


def _validate_model_combo(provider: str, model: str) -> tuple[str, str]:
    provider = provider.lower()
    try:
        registry.require_chat_model(provider, model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return provider, model


@router.post("/runs/batch", response_model=list[EvalRunOut])
async def create_eval_batch(
    body: EvalRunBatchCreate,
    user: User = Depends(require_roles("admin", "analyst")),
    queue=Depends(get_job_queue),
) -> list[EvalRunOut]:
    """A/B: run the same definition against several models at once."""
    definition = await _resolve_definition(body.definition_id, body.name)
    runs = []
    for choice in body.models:
        provider, model = _validate_model_combo(choice.provider, choice.model)
        run = await repo.create_eval_run(
            definition.slug,
            model_used=f"{provider}/{model}",
            definition_id=definition.id,
        )
        await queue.enqueue(
            "run_eval_job",
            _job_id=str(run.id),
            run_id=str(run.id),
            definition_id=str(definition.id),
            provider=provider,
            model=model,
            user_id=str(user.id),
        )
        runs.append(run)
    return [EvalRunOut.model_validate(r) for r in runs]


@router.get("/runs", response_model=list[EvalRunOut])
async def list_evals(
    limit: int = 20,
    _: User = Depends(get_current_user),
) -> list[EvalRunOut]:
    runs = await repo.list_eval_runs(limit=min(limit, 100))
    return [EvalRunOut.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=EvalRunOut)
async def get_eval(
    run_id: UUID,
    _: User = Depends(get_current_user),
) -> EvalRunOut:
    run = await repo.get_eval_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return EvalRunOut.model_validate(run)
