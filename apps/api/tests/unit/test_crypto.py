"""Unit tests for AES-GCM secret encryption at rest."""

from __future__ import annotations

from risklens.infrastructure.security.crypto import decrypt_secret, encrypt_secret


def test_roundtrip() -> None:
    plain = "sk-opencode-1234567890abcdef"
    token = encrypt_secret(plain)
    assert token != plain  # never stored in plaintext
    assert decrypt_secret(token) == plain


def test_random_nonce_means_distinct_tokens() -> None:
    assert encrypt_secret("mesma-chave") != encrypt_secret("mesma-chave")


def test_empty_string_roundtrip() -> None:
    assert decrypt_secret(encrypt_secret("")) == ""
