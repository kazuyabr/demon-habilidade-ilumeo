# RiskLens API + worker (same image, different command) — uv-based.
#
# Build:  docker build -f apps/api/Dockerfile apps/api
# The same image runs:
#   - API    : uvicorn risklens.main:app --host 0.0.0.0 --port 8010  (default CMD)
#   - worker : risklens-worker
#   - migrate: alembic upgrade head
#   - seed   : risklens-seed --with-samples

FROM python:3.12-slim AS base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# uv binary (pinned to the major.minor used to generate uv.lock)
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv

WORKDIR /app

# 1) install dependencies first (layer cached until pyproject/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 2) add application code + migrations
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ src/
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8010

CMD ["uvicorn", "risklens.main:app", "--host", "0.0.0.0", "--port", "8010"]
