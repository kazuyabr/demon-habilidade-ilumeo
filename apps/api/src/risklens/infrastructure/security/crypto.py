"""Encryption at rest for per-user provider credentials (AES-256-GCM).

The key comes from ``CREDENTIALS_ENC_KEY`` (base64 of 32 bytes); in dev it
falls back to a deterministic SHA-256 of ``JWT_SECRET``. Tokens are
``base64(nonce + ciphertext)``. The API never returns decrypted secrets.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from risklens.core.config import settings


def _key_bytes() -> bytes:
    if settings.credentials_enc_key:
        try:
            decoded = base64.b64decode(settings.credentials_enc_key, validate=True)
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
    return hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()


def encrypt_secret(plaintext: str) -> str:
    aesgcm = AESGCM(_key_bytes())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(token: str) -> str:
    raw = base64.b64decode(token)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(_key_bytes())
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
