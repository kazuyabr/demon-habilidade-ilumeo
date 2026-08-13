"""RiskLens API entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from risklens.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Risk intelligence platform — extraction, RAG, agents and evals.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
