"""Async SQLAlchemy engine and session management."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import pool as sa_pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from risklens.core.config import settings


class Base(DeclarativeBase):
    pass


# Tests use NullPool so connections are not reused across event loops
_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if settings.app_env == "test":
    _engine_kwargs["poolclass"] = sa_pool.NullPool
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20
engine = create_async_engine(settings.database_url, **_engine_kwargs)

SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session scoped to the request."""
    async with SessionFactory() as session:
        yield session
