"""Redis adapters: cache + pub/sub channel for live agent trace."""

from __future__ import annotations

from redis.asyncio import Redis

from risklens.core.config import settings

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def ping_redis() -> bool:
    try:
        return bool(await redis_client.ping())
    except Exception:
        return False


class RedisCache:
    async def get(self, key: str) -> str | None:
        return await redis_client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        await redis_client.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await redis_client.delete(key)


def channel_for_agent(run_id: str) -> str:
    return f"agent:{run_id}"
