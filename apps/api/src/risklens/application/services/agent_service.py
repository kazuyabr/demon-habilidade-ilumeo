"""Agent orchestration: plan → gather → analyze → review → final report.

A single "risk analyst" agent with explicit steps, each recorded to the DB
trace and published to Redis (SSE to the UI). Uses a JSON action protocol
(not native tool-calling) so it behaves identically across providers and on
small local models.

Flow:
1. plan   — decompose the question into retrieval sub-queries
2. gather — hybrid search per sub-query, dedupe evidence
3. analyze— extract factors/red flags from the evidence (JSON)
4. review — (feature flag) critic pass for contradictions/omissions
5. final  — synthesize the risk report with citations
"""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import BaseModel, Field

from risklens.application.ports import EmbeddingProvider, LLMProvider, VectorStore
from risklens.domain.entities import AgentStep
from risklens.infrastructure.ai import runtime
from risklens.infrastructure.ai.json_utils import parse_json_output
from risklens.infrastructure.cache.redis import channel_for_agent, redis_client
from risklens.infrastructure.db import repository as repo


class AgentReport(BaseModel):
    summary: str
    risk_score: int = Field(ge=0, le=100)
    risk_rating: str = Field(pattern="^[A-D]$")
    decision: str = Field(pattern="^(approve|conditional|decline)$")
    key_findings: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


async def _record(run_id: UUID, step: AgentStep) -> None:
    payload = step.to_dict()
    await repo.append_agent_step(run_id, payload)
    await redis_client.publish(channel_for_agent(str(run_id)), json.dumps(payload, ensure_ascii=False))


async def _json_call(llm: LLMProvider, *, system: str, user: str) -> dict:
    raw = await llm.complete(system=system, user=user)
    return parse_json_output(raw)


async def execute_agent(
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    *,
    run_id: UUID,
    question: str,
) -> dict:
    await _record(
        run_id,
        AgentStep(kind="plan", thought="Entendendo a pergunta e quebrando em sub-queries de busca.",
                  output=question),
    )

    # 1) plan
    plan = await _json_call(
        llm,
        system=(
            "Você é um planejador de uma análise de risco. Dada a pergunta do gestor, gere "
            "2 a 4 sub-perguntas de busca que, respondidas, cobrem a pergunta principal. "
            'Responda APENAS JSON: {"sub_queries": ["...", "..."]}.'
        ),
        user=f"Pergunta: {question}",
    )
    sub_queries = plan.get("sub_queries", [question])[:4]
    await _record(
        run_id,
        AgentStep(kind="plan", action="decompose", action_input=question,
                  observation=f"Sub-queries: {sub_queries}", output=json.dumps(sub_queries)),
    )

    # 2) gather
    cfg = runtime.get_cached_config()
    evidence: dict[str, dict] = {}
    for sub in sub_queries:
        embedding = (await embedder.embed_texts([sub]))[0]
        chunks = await vector_store.search(
            embedding,
            query_text=sub,
            hybrid=bool(cfg["rag_hybrid"]),
            limit=int(cfg["top_k"]),
        )
        for c in chunks:
            key = f"{c.document_id}:{c.content[:100]}"
            evidence[key] = {"doc": c.document_title, "content": c.content[:1200], "score": round(c.score, 3)}
    evidence_list = list(evidence.values())
    n_docs = len({e["doc"] for e in evidence_list})
    await _record(
        run_id,
        AgentStep(
            kind="retrieve",
            action="search",
            action_input=", ".join(sub_queries),
            observation=f"{len(evidence_list)} trechos recuperados de {n_docs} documentos.",
        ),
    )

    if not evidence_list:
        report = AgentReport(
            summary="Não foi possível recuperar evidências suficientes nos documentos indexados para esta pergunta.",
            risk_score=0,
            risk_rating="D",
            decision="conditional",
            key_findings=["Sem evidência nos documentos disponíveis."],
        )
        await _record(run_id, AgentStep(kind="final", output=report.model_dump_json()))
        await repo.finish_agent_run(run_id, status="completed", result=report.model_dump())
        return report.model_dump()

    context = "\n\n".join(f"[{i+1}] {e['doc']}:\n{e['content']}" for i, e in enumerate(evidence_list))

    # 3) analyze
    analysis = await _json_call(
        llm,
        system=(
            "Você é um analista de risco. Com base APENAS nas evidências citadas, produza análise JSON: "
            '{"risk_score": 0-100, "risk_rating": "A"|"B"|"C"|"D", "decision": "approve"|"conditional"|"decline", '
            '"key_findings": [string], "red_flags": [string]}'
        ),
        user=f"Evidências:\n{context}\n\nPergunta: {question}",
    )
    await _record(
        run_id,
        AgentStep(kind="analyze", thought="Consolidando evidências em score e achados.",
                  action_input=context[:2000], observation=json.dumps(analysis, ensure_ascii=False)),
    )

    # 4) review (feature flag)
    if cfg["ff_agent_review_enabled"]:
        review = await _json_call(
            llm,
            system=(
                "Você é um revisor sênior de risco. Critique a análise JSON recebida: identifique "
                "contradições, achados sem evidência e lacunas. Responda JSON: "
                '{"verdict": "approved"|"revised", "revision": {...}, "notes": [string]}'
            ),
            user=f"Análise:\n{json.dumps(analysis, ensure_ascii=False)}\n\nEvidências:\n{context[:4000]}",
        )
        if review.get("verdict") == "revised" and isinstance(review.get("revision"), dict):
            analysis = {**analysis, **review["revision"]}
        await _record(
            run_id,
            AgentStep(kind="review", thought="Revisão sênior aplicada.",
                      observation=json.dumps(review, ensure_ascii=False)),
        )

    # 5) final report
    citations = sorted({e["doc"] for e in evidence_list})
    try:
        final_raw = await llm.complete(
            system=(
                "Sintetize a análise e as evidências em um relatório final de risco conciso. "
                "Responda APENAS JSON com os campos: summary, risk_score, risk_rating, decision, "
                "key_findings (lista de strings), citations (títulos dos documentos usados)."
            ),
            user=f"Análise: {json.dumps(analysis, ensure_ascii=False)}\nEvidências: {context}",
        )
        report = AgentReport.model_validate(parse_json_output(final_raw))
    except Exception:
        report = AgentReport(
            summary=analysis.get("key_findings", [""])[0] if analysis.get("key_findings") else "Análise concluída.",
            risk_score=int(analysis.get("risk_score", 0)),
            risk_rating=analysis.get("risk_rating", "D"),
            decision=analysis.get("decision", "conditional"),
            key_findings=analysis.get("key_findings", []),
            citations=citations,
        )

    report_data = report.model_dump()
    report_data["citations"] = citations or report_data.get("citations", [])
    await _record(run_id, AgentStep(kind="final", output=json.dumps(report_data, ensure_ascii=False)))
    await repo.finish_agent_run(run_id, status="completed", result=report_data)
    return report_data
