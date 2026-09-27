"""Logging estructurado por etapa del pipeline RAG."""

import time
from contextlib import contextmanager

import structlog

logger = structlog.get_logger()


@contextmanager
def log_stage(stage: str, **context):
    """Envuelve una etapa del pipeline (reformulation/retrieval/context_assembly/
    generation/validation) con eventos stage.started/completed/failed y duration_ms.

    `request_id` y demas contexto de request ya estan bindeados via
    `structlog.contextvars` por el middleware de `app/main.py`; aqui solo se añade
    el nombre de la etapa y contexto propio de ella.
    """
    start = time.perf_counter()
    log = logger.bind(stage=stage, **context)
    log.info("stage.started")
    try:
        yield log
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log.info("stage.completed", duration_ms=duration_ms)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log.exception("stage.failed", duration_ms=duration_ms, error=str(exc))
        raise
