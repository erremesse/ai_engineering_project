"""Metricas de produccion (Sesion 16): cada peticion a un endpoint de estimacion
deja una linea JSON con latencia, tokens, coste y status. Sin LLM ni base de datos:
las funciones del pipeline se sustituyen por dobles que declaran un usage fijo.
"""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routers import estimate as estimate_router
from app.config import get_settings
from app.db.session import get_session
from app.generation.schemas import Estimate
from app.main import app
from app.observability import (
    add_usage,
    estimate_cost,
    estimation_endpoint,
    start_usage_tracking,
)
from app.routers import estimations as estimations_router

TOKEN = "test-service-token"
TRANSCRIPT = "Queremos una plataforma de comercio electronico con catalogo, carrito y checkout. " * 3
CAG_BODY = {
    "description": "Aplicacion web para gestionar reservas de salas",
    "project_type": "web_saas",
    "detail_level": "summary",
    "output_format": "narrative",
}


def _read_metrics(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def metrics_file(tmp_path, monkeypatch):
    path = tmp_path / "metrics" / "estimate_requests.jsonl"
    settings = get_settings()
    monkeypatch.setattr(settings, "METRICS_LOG_PATH", str(path))
    monkeypatch.setattr(settings, "AI_SERVICE_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "ESTIMATE_API_KEY", None)
    monkeypatch.setattr(settings, "LLM_PRICE_INPUT_PER_MTOK_USD", 2.0)
    monkeypatch.setattr(settings, "LLM_PRICE_OUTPUT_PER_MTOK_USD", 10.0)
    return path


@pytest.fixture
def client():
    async def _no_db():
        yield None

    app.dependency_overrides[get_session] = _no_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _fake_response(prompt_tokens: int, completion_tokens: int, model: str = "claude-sonnet-5"):
    return SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        model=model,
    )


def test_estimate_cost_uses_configured_prices(metrics_file):
    # 1M in * $2 + 0.5M out * $10
    assert estimate_cost(1_000_000, 500_000) == pytest.approx(7.0)


def test_usage_accumulates_across_llm_calls():
    usage = start_usage_tracking()
    add_usage(_fake_response(1000, 200))
    add_usage(_fake_response(3000, 800))
    assert (usage.prompt_tokens, usage.completion_tokens, usage.llm_calls) == (4000, 1000, 2)
    assert usage.model == "claude-sonnet-5"


@pytest.mark.parametrize(
    ("method", "path", "label"),
    [
        ("POST", "/v1/estimate/from-transcript", "/v1/estimate/from-transcript"),
        ("POST", "/api/v1/estimate", "/api/v1/estimate"),
        ("POST", "/api/v1/estimate/stream", "/api/v1/estimate/stream"),
        ("POST", "/api/v1/sessions/abc-123/estimate", "/api/v1/sessions/{session_id}/estimate"),
        ("GET", "/api/v1/sessions/abc-123", None),
        ("POST", "/v1/retrieval/search", None),
        ("GET", "/health", None),
    ],
)
def test_estimation_endpoint_classification(method, path, label):
    assert estimation_endpoint(method, path) == label


def test_rag_estimate_records_tokens_and_cost(client, metrics_file, monkeypatch):
    async def fake_estimate(session, transcript, idempotency_key=None):
        add_usage(_fake_response(10_000, 2_000))  # reformulation + generation, summed
        return Estimate(
            total_engineer_days=None,
            cost_breakdown=[],
            duration_weeks=None,
            sources=[],
            assumptions=[],
            confidence="insufficient",
            reasoning="sin contexto",
        )

    monkeypatch.setattr(estimate_router, "estimate_from_transcript", fake_estimate)
    response = client.post(
        "/v1/estimate/from-transcript",
        json={"transcript": TRANSCRIPT},
        headers={"X-Service-Token": TOKEN},
    )

    assert response.status_code == 200
    [record] = _read_metrics(metrics_file)
    assert record["endpoint"] == "/v1/estimate/from-transcript"
    assert record["status_code"] == 200
    assert (record["prompt_tokens"], record["completion_tokens"]) == (10_000, 2_000)
    assert record["estimated_cost_usd"] == pytest.approx(0.04)
    assert record["latency_ms"] >= 0


def test_pipeline_failure_is_recorded_as_502(client, metrics_file, monkeypatch):
    async def failing_estimate(session, transcript, idempotency_key=None):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(estimate_router, "estimate_from_transcript", failing_estimate)
    response = client.post(
        "/v1/estimate/from-transcript",
        json={"transcript": TRANSCRIPT},
        headers={"X-Service-Token": TOKEN},
    )

    assert response.status_code == 502
    assert _read_metrics(metrics_file)[0]["status_code"] == 502


def test_rejected_token_is_recorded_as_401(client, metrics_file):
    response = client.post("/v1/estimate/from-transcript", json={"transcript": TRANSCRIPT})
    assert response.status_code == 401
    [record] = _read_metrics(metrics_file)
    assert record["status_code"] == 401
    assert record["estimated_cost_usd"] == 0


def test_streaming_estimate_counts_tokens_after_body_is_sent(client, metrics_file, monkeypatch):
    from app.observability import add_usage_counts

    async def fake_stream(system, user):
        yield "Fase 1..."
        add_usage_counts(500, 1_500, "claude-sonnet-5")  # usage arrives with the last chunk
        yield "\x00{}"

    monkeypatch.setattr(estimations_router, "stream_estimation", fake_stream)
    response = client.post("/api/v1/estimate/stream", json=CAG_BODY, headers={"X-Service-Token": TOKEN})

    assert response.status_code == 200
    [record] = _read_metrics(metrics_file)
    assert record["endpoint"] == "/api/v1/estimate/stream"
    assert (record["prompt_tokens"], record["completion_tokens"]) == (500, 1_500)


def test_non_estimation_routes_emit_no_metrics(client, metrics_file):
    assert client.get("/health").status_code == 200
    assert not metrics_file.exists()
