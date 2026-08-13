"""Auth routes: OAuth2 password login → access+refresh tokens, refresh, me."""

from __future__ import annotations

from uuid import UUID

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from risklens.api.deps import get_current_user
from risklens.api.schemas import TokenPair, UserOut
from risklens.core.security import create_token, decode_token, verify_password
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
