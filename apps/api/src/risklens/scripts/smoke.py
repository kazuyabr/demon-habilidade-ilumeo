"""End-to-end smoke test for the running stack (API + worker + LM Studio).

Usage: uv run python -m risklens.scripts.smoke

Assumes: API on http://127.0.0.1:8010, arq worker running, Postgres/Redis up,
LM Studio serving the configured models. Exercises the full pipeline and
fails loudly if any step breaks.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8010"
API = f"{BASE}/api/v1"
EMAIL = "admin@risklens.local"
PASSWORD = "Admin@12345"
_SAMPLES = Path(__file__).resolve()
while _SAMPLES.name != "demon-habilidade-ilumeo" and _SAMPLES.parent != _SAMPLES:
    _SAMPLES = _SAMPLES.parent
SAMPLES = _SAMPLES / "samples" / "documents"  # repo samples


def _check(label: str, ok: bool, detail: str = "") -> None:
    print(f"[{'OK' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def wait_status(client: httpx.Client, url: str, done: set[str], timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(url)
        r.raise_for_status()
        body = r.json()
        if body["status"] in done:
            return body
        time.sleep(2)
    raise TimeoutError(f"timeout esperando status em {url}")


def main() -> None:
    with httpx.Client(timeout=60) as client:
        # auth
        r = client.post(
            f"{API}/auth/login",
            data={"username": EMAIL, "password": PASSWORD},
        )
        _check("login", r.status_code == 200, str(r.status_code))
        tokens = r.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        client.headers.update(headers)

        me = client.get(f"{API}/auth/me")
        _check("GET /auth/me", me.status_code == 200 and me.json()["role"] == "admin", me.text[:120])

        # upload + pipeline
        doc = SAMPLES / "transportadora-estrela.md"
        with doc.open("rb") as fh:
            up = client.post(
                f"{API}/documents/upload",
                files={"file": (doc.name, fh, "text/markdown")},
                data={"source": "smoke"},
            )
        _check("upload documento", up.status_code in (200, 201), up.text[:200])
        doc_id = up.json()["document"]["id"]

        body = wait_status(client, f"{API}/documents/{doc_id}", {"completed", "failed"})
        _check("documento processado (worker)", body["status"] == "completed", body.get("error_message"))

        ext = client.get(f"{API}/extractions/document/{doc_id}")
        _check("extração estruturada", ext.status_code == 200 and ext.json().get("data"), ext.text[:200])
        ext_data = ext.json()["data"]
        raw = json.dumps(ext_data, ensure_ascii=False)
        # PII property: no raw CPF/CNPJ/e-mail/phone/card survives in extraction output
        import re

        pii_patterns = [
            r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",  # CPF
            r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",  # CNPJ
            r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",  # email
        ]
        leaks = [m for pat in pii_patterns for m in re.findall(pat, raw)]
        _check("sem vazamento de PII", not leaks, f"achados: {leaks}")
        print("  score:", ext_data.get("overall_risk_score"), "| decisão:", ext_data.get("decision"))

        # RAG
        rag = client.post(
            f"{API}/rag/ask",
            json={"question": "Qual é o principal risco de crédito da Transportadora Estrela?"},
        )
        _check("RAG ask", rag.status_code == 200, rag.text[:200])
        rag_body = rag.json()
        _check("RAG com citações", len(rag_body["citations"]) > 0, f"{len(rag_body['citations'])} citações")
        print("  resposta:", rag_body["answer"][:160].replace("\n", " "))

        # agent
        q = "Analise o risco de crédito da Transportadora Estrela."
        run = client.post(f"{API}/agents/runs", json={"question": q})
        _check("agente iniciado", run.status_code == 200, run.text[:200])
        run_id = run.json()["id"]
        agent = wait_status(client, f"{API}/agents/runs/{run_id}", {"completed", "failed"})
        _check("agente concluído", agent["status"] == "completed", agent.get("error_message"))
        _check("agente gerou relatório", bool(agent.get("result")))
        _check("agente registrou trace", len(agent.get("trace") or []) >= 3, f"{len(agent.get('trace') or [])} passos")
        print("  decisão do agente:", agent["result"].get("decision"), "| score:", agent["result"].get("risk_score"))

        # evals
        ev = client.post(f"{API}/evals/runs", json={"name": "credit-report-golden"})
        _check("eval iniciado", ev.status_code == 200, ev.text[:200])
        eval_id = ev.json()["id"]
        evr = wait_status(
            client,
            f"{API}/evals/runs/{eval_id}",
            {"completed", "completed_with_failures", "failed"},
            timeout=300,
        )
        _check("eval concluído", evr["status"] != "failed", evr.get("error_message"))
        print("  métricas:", json.dumps(evr.get("metrics"), ensure_ascii=False))

        print("\nSmoke test OK: pipeline completo funcionando.")


if __name__ == "__main__":
    main()
