"""RiskLens API entrypoint — wires routers, telemetry and middleware."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from risklens.api.routers import admin, agents, auth, documents, evals, extractions, rag
from risklens.core.config import settings
from risklens.core.telemetry import init_telemetry

logger = logging.getLogger("risklens.api")

API_V1 = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_telemetry(app)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Risk intelligence platform — extraction, RAG, agents and evals.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak internals to clients (OWASP: error handling / information disclosure)
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor"})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


for router in (auth, documents, extractions, rag, agents, evals, admin):
    app.include_router(router.router, prefix=API_V1)
