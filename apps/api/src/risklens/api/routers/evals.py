"""Eval routes: run evals against the golden set and inspect results."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from risklens.api.deps import get_current_user, get_job_queue, get_llm
from risklens.api.schemas import EvalRunCreate, EvalRunOut
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.db.models import User

router = APIRouter(prefix="/evals", tags=["evals"])


@router.post("/runs", response_model=EvalRunOut)
async def create_eval(
    body: EvalRunCreate,
    user: User = Depends(get_current_user),
    llm=Depends(get_llm),
    queue=Depends(get_job_queue),
) -> EvalRunOut:
    if user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Permissão insuficiente")
    run = await repo.create_eval_run(body.name, model_used=llm.model)
    await queue.enqueue("run_eval_job", _job_id=str(run.id), run_id=str(run.id))
    return EvalRunOut.model_validate(run)


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
