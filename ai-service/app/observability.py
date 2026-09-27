"""Metricas de produccion por peticion de estimacion (Sesion 16).

Cada llamada a un endpoint de estimacion (RAG /v1/estimate/from-transcript y los
CAG /api/v1/estimate, /api/v1/estimate/stream, /api/v1/sessions/{id}/estimate)
deja una senal `estimate_request` con latencia,
tokens, coste estimado y status HTTP. Va a dos sitios:

- el log estructurado (structlog), como el resto de eventos del servicio;
- una linea JSON en METRICS_LOG_PATH, que es lo que lee eval/dashboard.py.

Los tokens se acumulan por peticion con un ContextVar: el middleware crea el
acumulador y cada llamada al LLM (reformulacion, generacion, reintentos) suma su
`response.usage`. El acumulador es un objeto mutable a proposito — Starlette
ejecuta la app en otra task con una *copia* del contexto, asi que reasignar el
ContextVar dentro no se veria desde el middleware, pero mutar el objeto si.
"""

import json
import re
from collections.abc import AsyncIterator, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import structlog

from app.config import get_settings

logger = structlog.get_logger("ai-service.metrics")


@dataclass
class UsageAccumulator:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0
    model: str | None = None


_usage: ContextVar[UsageAccumulator | None] = ContextVar("llm_usage", default=None)


def start_usage_tracking() -> UsageAccumulator:
    accumulator = UsageAccumulator()
    _usage.set(accumulator)
    return accumulator


def add_usage(response) -> None:
    """Suma el `usage` de una respuesta de litellm a la peticion en curso.

    No-op fuera de una peticion instrumentada (scripts, tests) o si el proveedor
    no devuelve usage.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    add_usage_counts(
        getattr(usage, "prompt_tokens", 0) or 0,
        getattr(usage, "completion_tokens", 0) or 0,
        getattr(response, "model", None),
    )


def add_usage_counts(prompt_tokens: int, completion_tokens: int, model: str | None) -> None:
    """Variante para streaming, donde el usage llega en el ultimo chunk."""
    accumulator = _usage.get()
    if accumulator is None:
        return
    accumulator.prompt_tokens += prompt_tokens
    accumulator.completion_tokens += completion_tokens
    accumulator.llm_calls += 1
    accumulator.model = model or accumulator.model


# Estimation endpoints that emit metrics, labelled by route template so the
# dashboard can group them (session ids would otherwise make every path unique).
_ESTIMATION_ROUTES = [
    (re.compile(r"^/v1/estimate/from-transcript$"), "/v1/estimate/from-transcript"),
    (re.compile(r"^/api/v1/estimate$"), "/api/v1/estimate"),
    (re.compile(r"^/api/v1/estimate/stream$"), "/api/v1/estimate/stream"),
    (re.compile(r"^/api/v1/sessions/[^/]+/estimate$"), "/api/v1/sessions/{session_id}/estimate"),
]


def estimation_endpoint(method: str, path: str) -> str | None:
    if method != "POST":
        return None
    for pattern, label in _ESTIMATION_ROUTES:
        if pattern.match(path):
            return label
    return None


async def metered_body(body: AsyncIterator[bytes], on_complete: Callable[[], None]) -> AsyncIterator[bytes]:
    """Reemite el cuerpo de la respuesta y llama a `on_complete` al terminar de enviarlo."""
    try:
        async for chunk in body:
            yield chunk
    finally:
        on_complete()


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Coste en USD derivado del recuento de tokens y del precio configurado."""
    settings = get_settings()
    return round(
        prompt_tokens * settings.LLM_PRICE_INPUT_PER_MTOK_USD / 1_000_000
        + completion_tokens * settings.LLM_PRICE_OUTPUT_PER_MTOK_USD / 1_000_000,
        6,
    )


def record_request_metrics(
    request_id: str,
    endpoint: str,
    status_code: int,
    latency_ms: float,
    usage: UsageAccumulator,
) -> dict:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request_id": request_id,
        "endpoint": endpoint,
        "status_code": status_code,
        "latency_ms": round(latency_ms, 1),
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "llm_calls": usage.llm_calls,
        "model": usage.model,
        "estimated_cost_usd": estimate_cost(usage.prompt_tokens, usage.completion_tokens),
    }
    logger.info("estimate_request", **record)
    _append_jsonl(record)
    return record


def _append_jsonl(record: dict) -> None:
    path = get_settings().METRICS_LOG_PATH
    if not path:
        return
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        # Losing a metric must never break the estimate the user is waiting for.
        logger.warning("metrics_write_failed", path=path, error_msg=str(exc))
