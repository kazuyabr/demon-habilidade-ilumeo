"""API dependencies: authentication, RBAC, shared providers."""

from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from risklens.application.ports import (
    DocumentStorage,
    EmbeddingProvider,
    JobQueue,
    LLMProvider,
    VectorStore,
)
from risklens.core.security import decode_token
from risklens.infrastructure.ai import runtime
from risklens.infrastructure.ai.llm_provider import build_chat_provider, build_embedding_provider
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.db.session import get_session
from risklens.infrastructure.queue.queue import ArqJobQueue
from risklens.infrastructure.storage.fs_storage import FsDocumentStorage
from risklens.infrastructure.vector.pgvector_store import PgVectorStore

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_llm: LLMProvider | None = None
_embedder: EmbeddingProvider | None = None
_llm_version: int = -1
_embedder_version: int = -1
_storage: DocumentStorage = FsDocumentStorage()
_vector_store: VectorStore = PgVectorStore()
_job_queue: JobQueue = ArqJobQueue()


async def get_llm() -> LLMProvider:
    global _llm, _llm_version
    version = await runtime.get_config_version()
    if _llm is None or version != _llm_version:
        _llm = build_chat_provider()
        _llm_version = version
    return _llm


async def get_embedder() -> EmbeddingProvider:
    global _embedder, _embedder_version
    version = await runtime.get_config_version()
    if _embedder is None or version != _embedder_version:
        _embedder = build_embedding_provider()
        _embedder_version = version
    return _embedder


def get_storage() -> DocumentStorage:
    return _storage


def get_vector_store() -> VectorStore:
    return _vector_store


def get_job_queue() -> JobQueue:
    return _job_queue


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
):
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exc
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise credentials_exc from None

    user = await session.get(repo.m.User, user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


def require_roles(*roles: str):
    async def _dep(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente")
        return user

    return _dep
