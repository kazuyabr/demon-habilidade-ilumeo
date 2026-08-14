"""Auth routes: OAuth2 password login → access+refresh tokens, refresh, me,
and per-user BYOK credentials."""

from __future__ import annotations

from uuid import UUID

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from risklens.api.deps import get_current_user
from risklens.api.schemas import CredentialSummary, CredentialUpdate, TokenPair, UserOut
from risklens.application.services import credential_service
from risklens.core.security import create_token, decode_token, verify_password
from risklens.infrastructure.ai import registry
from risklens.infrastructure.db import repository as repo
from risklens.infrastructure.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenPair:
    user = await repo.get_user_by_email(form.username)
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo")

    return TokenPair(
        access_token=create_token(user_id=user.id, role=user.role, token_type="access"),
        refresh_token=create_token(user_id=user.id, role=user.role, token_type="refresh"),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("not a refresh token")
        user_id = payload["sub"]
    except (pyjwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido") from None

    user = await repo.get_user_by_id(UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")

    return TokenPair(
        access_token=create_token(user_id=user.id, role=user.role, token_type="access"),
        refresh_token=create_token(user_id=user.id, role=user.role, token_type="refresh"),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/credentials", response_model=list[CredentialSummary])
async def list_my_credentials(user: User = Depends(get_current_user)) -> list[CredentialSummary]:
    return [CredentialSummary(**c) for c in await credential_service.list_credentials(user.id)]


@router.put("/credentials/{provider}", response_model=CredentialSummary)
async def upsert_my_credential(
    provider: str,
    body: CredentialUpdate,
    user: User = Depends(get_current_user),
) -> CredentialSummary:
    try:
        p = registry.resolve_provider(provider)
    except ValueError:
        raise HTTPException(status_code=404, detail="provider desconhecido") from None
    if not (p["chat"] or p["embeddings"]):
        raise HTTPException(status_code=400, detail="provider não aceita credenciais")

    if body.api_key is None and body.base_url is None:
        raise HTTPException(status_code=400, detail="informe api_key e/ou base_url")

    result = await credential_service.upsert_credential(
        user.id, provider, api_key=body.api_key, base_url=body.base_url
    )
    return CredentialSummary(**result)


@router.delete("/credentials/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_credential(
    provider: str,
    user: User = Depends(get_current_user),
) -> None:
    await credential_service.delete_credential(user.id, provider)
