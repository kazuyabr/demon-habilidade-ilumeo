"""PII redaction for extraction output.

Applied to every string field of a validated extraction before persistence —
the API never returns raw PII. Regex-based: fast, deterministic and
explainable (vs. an NER model). Trade-off documented in .vibecoding/docs/10.
"""

from __future__ import annotations

import re

# CPF: 123.456.789-00 or 12345678900
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
# CNPJ: 12.345.678/0001-90 or plain 14 digits
_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
# Email
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Phone: +55 (11) 98765-4321, (11) 98765-4321, 11 98765-4321
_PHONE = re.compile(r"\+?\d{2}\s?\(?\d{2}\)?\s?\d{4,5}-?\d{4}")
# Credit card: 16 digits (with optional spaces)
_CARD = re.compile(r"\b(?:\d[ -]*){13,19}\b")


def redact_text(text: str) -> str:
    text = _CNPJ.sub("[REDACTED_CNPJ]", text)
    text = _CPF.sub("[REDACTED_CPF]", text)
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _PHONE.sub("[REDACTED_PHONE]", text)
    # card after phone to avoid overlapping patterns
    text = _CARD.sub("[REDACTED_CARD]", text)
    return text


def redact_value(value):
    """Recursively redact all strings in a JSON-able structure."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    return value
