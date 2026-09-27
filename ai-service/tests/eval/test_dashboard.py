"""Agregaciones del dashboard de produccion (Sesion 16)."""

import json

import pytest

from eval.dashboard import error_rate, load_records, p95, render_html, summarize


def _record(ts: str, status: int = 200, latency_ms: float = 1000.0, cost: float = 0.01,
            endpoint: str = "/v1/estimate/from-transcript") -> dict:
    return {"ts": ts, "request_id": ts[-2:], "endpoint": endpoint, "status_code": status,
            "latency_ms": latency_ms, "prompt_tokens": 1000, "completion_tokens": 500,
            "llm_calls": 2, "model": "claude-sonnet-5", "estimated_cost_usd": cost}


def test_p95_nearest_rank():
    assert p95(list(range(1, 101))) == 95
    assert p95([5.0]) == 5.0
    assert p95([]) is None


def test_error_rate_counts_every_non_200():
    records = [_record("t1"), _record("t2", 401), _record("t3", 502), _record("t4")]
    assert error_rate(records) == 0.5
    assert error_rate([]) is None


def test_mean_cost_only_counts_successful_estimates():
    records = [_record("t1", cost=0.02), _record("t2", cost=0.04), _record("t3", 401, cost=0.0)]
    summary = summarize(records)
    assert summary["mean_cost_usd"] == pytest.approx(0.03)
    assert summary["total_cost_usd"] == pytest.approx(0.06)


def test_load_records_filters_and_sorts(tmp_path):
    path = tmp_path / "m.jsonl"
    rows = [_record("2026-09-27T10:00:02"), _record("2026-09-26T10:00:00"),
            _record("2026-09-27T10:00:01", endpoint="/api/v1/estimate")]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n\n", encoding="utf-8")

    assert [r["ts"] for r in load_records(path)] == sorted(r["ts"] for r in rows)
    assert len(load_records(path, since="2026-09-27")) == 2
    assert len(load_records(path, endpoint="/api/v1/estimate")) == 1


def test_render_html_handles_empty_and_populated():
    assert "No hay peticiones" in render_html([], "m.jsonl")
    page = render_html([_record("t1"), _record("t2", 502, latency_ms=3000.0)], "m.jsonl")
    assert "<svg" in page and "HTTP 502" in page
