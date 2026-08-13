"""Structured extraction from unstructured document text.

Pipeline: build prompt from schema JSON Schema → LLM → robust JSON parse →
Pydantic validation → repair retry (max 2) → PII redaction. The repair
loop is the resilience story: local models wrap/truncate JSON often, so we
validate and fix rather than fail.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from risklens.application.ports import LLMProvider
from risklens.domain.schemas import SCHEMA_REGISTRY
from risklens.infrastructure.ai.json_utils import parse_json_output
from risklens.infrastructure.pii.redactor import redact_value

MAX_TEXT_CHARS = 15000
MAX_REPAIR_ATTEMPTS = 2


def _build_system_prompt(schema_name: str) -> str:
    schema = SCHEMA_REGISTRY[schema_name].model_json_schema()
    schema_json = json.dumps(schema, ensure_ascii=False)
    return (
        "Você é um analista de risco especialista em due diligence. "
        "Extraia do relatório fornecido os campos estruturados pedidos.\n"
        "Responda APENAS com um objeto JSON válido, sem markdown, sem texto fora do JSON.\n"
        "Se um dado não estiver no texto, use null ou lista vazia — nunca invente.\n"
        f"Seguindo exatamente este JSON Schema:\n{schema_json}"
    )


async def extract_from_text(
    llm: LLMProvider,
    *,
    text: str,
    schema_name: str = "credit_report",
) -> tuple[dict, float, str]:
    if schema_name not in SCHEMA_REGISTRY:
        raise ValueError(f"unknown schema: {schema_name}")
    model_cls = SCHEMA_REGISTRY[schema_name]

    truncated = text[:MAX_TEXT_CHARS]
    system = _build_system_prompt(schema_name)
    user = f"Relatório:\n---\n{truncated}\n---\n\nExtraia o JSON."

    raw = await llm.complete(system=system, user=user)
    last_error = ""

    for _attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        try:
            payload = parse_json_output(raw)
            parsed = model_cls.model_validate(payload)
            data = parsed.model_dump()
            redacted = redact_value(data)
            return redacted, float(data.get("confidence", 0.0)), raw
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)[:2000]
            raw = await llm.complete(
                system=(
                    "Você corrige JSON. Recebeu a saída anterior inválida e o erro de validação. "
                    "Substitua valores null em campos obrigatórios por strings vazias ou valores "
                    "derivados do texto. Responda APENAS com o JSON corrigido, completo, sem markdown.\n"
                    f"JSON Schema:\n{json.dumps(model_cls.model_json_schema(), ensure_ascii=False)}"
                ),
                user=(
                    f"Saída anterior inválida:\n{raw[:6000]}\n\n"
                    f"Erro:\n{last_error}\n\nReescreva o JSON corrigido completo."
                ),
            )

    raise ValueError(f"extraction failed after repair attempts: {last_error}")
