"""Per-user provider credentials (BYOK) — host + api-key encrypted at rest.

Resolution: a user's credential for a provider overrides the env default for
the fields they set; unset fields fall back to the deployment env. Secrets
are only decrypted at use time and never returned by the API.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from risklens.infrastructure.ai import runtime
from risklens.infrastructure.ai.llm_provider import (
    build_chat_provider_for,
    build_embedding_provider_for,
    resolve_chat_endpoint,
    resolve_embed_endpoint,
)
from risklens.infrastructure.db import models as m
from risklens.infrastructure.db.session import SessionFactory
from risklens.infrastructure.security.crypto import decrypt_secret, encrypt_secret


async def get_credential(user_id: UUID, provider: str) -> m.UserCredential | None:
    async with SessionFactory() as session:
        return await session.get(m.UserCredential, (user_id, provider))


async def list_credentials(user_id: UUID) -> list[dict]:
    async with SessionFactory() as session:
        result = await session.execute(
            select(m.UserCredential)
            .where(m.UserCredential.user_id == user_id)
            .order_by(m.UserCredential.provider)
        )
        rows = result.scalars().all()
    return [
        {
            "provider": r.provider,
            "has_api_key": bool(r.api_key_encrypted),
            "api_key_last4": r.api_key_last4,
            "has_base_url": bool(r.base_url_encrypted),
            "base_url": decrypt_secret(r.base_url_encrypted) if r.base_url_encrypted else None,
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


async def upsert_credential(
    user_id: UUID,
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict:
    api_key_enc = encrypt_secret(api_key) if api_key else None
    base_url_enc = encrypt_secret(base_url) if base_url else None
    last4 = api_key[-4:] if api_key else None

    async with SessionFactory() as session:
        row = await session.get(m.UserCredential, (user_id, provider))
        if row is None:
            session.add(
                m.UserCredential(
                    user_id=user_id,
                    provider=provider,
                    api_key_encrypted=api_key_enc,
                    base_url_encrypted=base_url_enc,
                    api_key_last4=last4,
                )
            )
        else:
            if api_key_enc is not None:
                row.api_key_encrypted = api_key_enc
                row.api_key_last4 = last4
            if base_url_enc is not None:
                row.base_url_encrypted = base_url_enc
        await session.commit()
    return await summary(user_id, provider)


async def delete_credential(user_id: UUID, provider: str) -> None:
    async with SessionFactory() as session:
        row = await session.get(m.UserCredential, (user_id, provider))
        if row is not None:
            await session.delete(row)
            await session.commit()


async def summary(user_id: UUID, provider: str) -> dict:
    cred = await get_credential(user_id, provider)
    return {
        "provider": provider,
        "has_api_key": bool(cred and cred.api_key_encrypted),
        "api_key_last4": cred.api_key_last4 if cred else None,
        "has_base_url": bool(cred and cred.base_url_encrypted),
        "base_url": decrypt_secret(cred.base_url_encrypted) if cred and cred.base_url_encrypted else None,
        "updated_at": cred.updated_at.isoformat() if cred else None,
    }


async def get_effective_chat_endpoint(user_id: UUID, provider: str) -> tuple[str, str]:
    base_url, api_key = resolve_chat_endpoint(provider)
    cred = await get_credential(user_id, provider)
    if cred:
        if cred.base_url_encrypted:
            base_url = decrypt_secret(cred.base_url_encrypted)
        if cred.api_key_encrypted:
            api_key = decrypt_secret(cred.api_key_encrypted)
    return base_url, api_key


async def get_effective_embed_endpoint(user_id: UUID, provider: str) -> tuple[str, str, int | None]:
    base_url, api_key, dims = resolve_embed_endpoint(provider)
    cred = await get_credential(user_id, provider)
    if cred:
        if cred.base_url_encrypted:
            base_url = decrypt_secret(cred.base_url_encrypted)
        if cred.api_key_encrypted:
            api_key = decrypt_secret(cred.api_key_encrypted)
    return base_url, api_key, dims


async def build_user_chat_provider(user_id: UUID):
    """Chat provider for a user's request/job, using their credentials
    (env defaults where they did not set their own)."""
    cfg = runtime.get_cached_config()
    provider = str(cfg["chat_provider"]).lower()
    model = str(cfg["chat_model"])
    base_url, api_key = await get_effective_chat_endpoint(user_id, provider)
    return build_chat_provider_for(provider, model, base_url=base_url, api_key=api_key)


async def build_user_embedding_provider(user_id: UUID):
    cfg = runtime.get_cached_config()
    provider = str(cfg["embedding_provider"]).lower()
    model = str(cfg["embedding_model"])
    base_url, api_key, _dims = await get_effective_embed_endpoint(user_id, provider)
    return build_embedding_provider_for(provider, model, base_url=base_url, api_key=api_key)
