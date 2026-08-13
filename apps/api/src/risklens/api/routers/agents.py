"""Agent routes: start runs, list, detail, and live trace via SSE.

SSE subscribes to the Redis channel the worker publishes each step to; the DB
trace is the source of truth (replayed at subscribe time), pub/sub is the
live delta. Near-real-time trace without missing events on reconnect.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from risklens.api.deps import get_current_user, get_job_queue, get_llm, get_vector_store
from risklens.api.schemas import AgentRunCreate, AgentRunOut
from risklens.infrastructure.cache.redis import channel_for_agent, redis_client
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.db.models import User

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/runs", response_model=AgentRunOut)
async def create_run(
    body: AgentRunCreate,
    user: User = Depends(get_current_user),
    llm=Depends(get_llm),
    queue=Depends(get_job_queue),
    vector_store=Depends(get_vector_store),
) -> AgentRunOut:
    run = await repo.create_agent_run(body.question, created_by=user.id, model_used=llm.model)
    await queue.enqueue("run_agent_job", _job_id=str(run.id), run_id=str(run.id))
    return AgentRunOut.model_validate(run)


@router.get("/runs", response_model=list[AgentRunOut])
async def list_runs(
    limit: int = 20,
    _: User = Depends(get_current_user),
) -> list[AgentRunOut]:
    runs = await repo.list_agent_runs(limit=min(limit, 100))
    return [AgentRunOut.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=AgentRunOut)
async def get_run(
    run_id: UUID,
    _: User = Depends(get_current_user),
) -> AgentRunOut:
    run = await repo.get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    return AgentRunOut.model_validate(run)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: UUID, _: User = Depends(get_current_user)) -> StreamingResponse:
    run = await repo.get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")

    channel = channel_for_agent(str(run_id))

    async def event_stream():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            # replay DB trace (source of truth)
            current = await repo.get_agent_run(run_id)
            if current:
                for step in current.trace or []:
                    yield f"data: {json.dumps(step, ensure_ascii=False)}\n\n"
                if current.status != "running":
                    yield "event: done\ndata: {}\n\n"
                    return
            # live delta
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    yield f"data: {msg['data']}\n\n"
                state = await repo.get_agent_run(run_id)
                if state and state.status != "running":
                    yield "event: done\ndata: {}\n\n"
                    break
        finally:
            await pubsub.unsubscribe(channel)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
