"""arq JobQueue adapter (API side) — enqueues jobs for the worker.

Idempotency: ``_job_id`` ties a job to its aggregate id (document_id,
agent_run_id, eval_run_id), so re-enqueueing the same aggregate does not
create duplicate work.
"""

from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from risklens.core.config import settings


class ArqJobQueue:
    def __init__(self) -> None:
        self._pool: ArqRedis | None = None

    async def _pool_or_create(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        return self._pool

    async def enqueue(self, function_name: str, *, _job_id: str, **kwargs) -> None:
        pool = await self._pool_or_create()
        await pool.enqueue_job(function_name, **kwargs, _job_id=_job_id)
