# Servicio IA (FastAPI) — Sesion 15.
# Multi-stage: uv resolves the locked deps in a builder stage; the runtime image
# only carries the venv + code and runs as a non-root user.

FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies first to leverage layer caching (torch is ~1GB even CPU-only).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


FROM python:3.11-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY alembic.ini pyproject.toml docker-entrypoint.sh ./

# HF_HOME points at a named volume in compose so the reranker model downloaded
# on first use survives `docker compose down`.
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/.cache/huggingface

RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh && \
    mkdir -p "$HF_HOME" && chown -R app:app /app

USER app

EXPOSE 8000

# /health does NOT call the LLM nor the DB and is exempt from X-Service-Token.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
