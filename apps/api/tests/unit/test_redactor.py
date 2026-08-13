"""Unit tests for PII redaction — no infrastructure required."""

from __future__ import annotations

from risklens.infrastructure.pii.redactor import redact_text, redact_value


def test_cpf_is_masked() -> None:
    assert redact_text("CPF 123.456.789-00 do sócio") == "CPF [REDACTED_CPF] do sócio"


def test_cnpj_is_masked() -> None:
    assert redact_text("CNPJ 12.345.678/0001-90") == "CNPJ [REDACTED_CNPJ]"


def test_cnpj_plain_digits() -> None:
    assert redact_text("doc 12345678000190 fim") == "doc [REDACTED_CNPJ] fim"


def test_email_is_masked() -> None:
    assert redact_text("fale com joao@empresa.com.br hoje") == "fale com [REDACTED_EMAIL] hoje"


def test_phone_is_masked() -> None:
    assert redact_text("tel +55 11 98765-4321 ok") == "tel [REDACTED_PHONE] ok"


def test_redact_value_recurses() -> None:
    data = {
        "company": "Acme",
        "contact": {"email": "a@b.com", "cnpj": "12.345.678/0001-90"},
        "tags": ["x", "sócio cpf 123.456.789-00"],
    }
    out = redact_value(data)
    assert out["contact"]["email"] == "[REDACTED_EMAIL]"
    assert out["contact"]["cnpj"] == "[REDACTED_CNPJ]"
    assert "123.456.789-00" not in out["tags"][1]
    assert out["company"] == "Acme"  # untouched


def test_plain_text_unchanged() -> None:
    text = "Receita estável, sem ocorrências."
    assert redact_text(text) == text
