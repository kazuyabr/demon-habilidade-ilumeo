"""Unit tests for JWT + Argon2 security primitives."""

from __future__ import annotations

from uuid import uuid4

import jwt as pyjwt
import pytest

from risklens.core.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("senha-forte-123")
    assert hashed != "senha-forte-123"
    assert verify_password("senha-forte-123", hashed)
    assert not verify_password("errada", hashed)


def test_token_roundtrip() -> None:
    uid = uuid4()
    token = create_token(user_id=uid, role="admin", token_type="access")
    payload = decode_token(token)
    assert payload["sub"] == str(uid)
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_token_type_distinct() -> None:
    access = create_token(user_id=uuid4(), role="viewer", token_type="access")
    refresh = create_token(user_id=uuid4(), role="viewer", token_type="refresh")
    assert decode_token(access)["type"] == "access"
    assert decode_token(refresh)["type"] == "refresh"


def test_expired_token_rejected() -> None:
    import time

    from risklens.core import security

    now = int(time.time())
    # craft a token already expired
    token = create_token(user_id=uuid4(), role="admin", token_type="access")
    payload = decode_token(token)
    payload["exp"] = now - 10
    expired = pyjwt.encode(payload, security.settings.jwt_secret, algorithm="HS256")
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(expired)
