"""Harness de evaluacion (Sesion 16): la logica de comparacion y agregacion, sin red.

Y un test de contrato sobre el propio golden set, para que un caso mal escrito se
detecte en CI y no a mitad de una ejecucion que consume tokens.
"""

import pytest

from eval.run_eval import DEFAULT_GOLDEN_SET, evaluate_case, load_golden_set, summarize

ESTIMATION_CASE = {"id": "c-est", "expected_engineer_days": 60, "acceptable_range": [36, 100]}
ABSTENTION_CASE = {"id": "c-abs", "expected_engineer_days": None, "acceptable_range": None, "expect_abstention": True}


def _ok(body: dict, latency_ms: float = 1000.0) -> dict:
    return {"status": 200, "body": body, "latency_ms": latency_ms, "error": None}


def _estimate(days, confidence="medium", sources=1) -> dict:
    return {
        "total_engineer_days": days,
        "confidence": confidence,
        "sources": [{"source_id": i, "relevance": "primary", "used_for": "x"} for i in range(sources)],
    }


INSUFFICIENT = {"total_engineer_days": None, "confidence": "insufficient", "sources": []}


def test_estimate_within_range_passes():
    result = evaluate_case(ESTIMATION_CASE, _ok(_estimate(80)))
    assert result["passed"] is True
    assert result["abs_error"] == 20
    assert result["grounded"] is True


def test_estimate_out_of_range_fails_but_reports_error_size():
    result = evaluate_case(ESTIMATION_CASE, _ok(_estimate(140)))
    assert result["passed"] is False
    assert result["abs_error"] == 80


def test_range_bounds_are_inclusive():
    assert evaluate_case(ESTIMATION_CASE, _ok(_estimate(36)))["passed"]
    assert evaluate_case(ESTIMATION_CASE, _ok(_estimate(100)))["passed"]


def test_abstaining_on_an_estimation_case_fails_unless_allowed():
    assert evaluate_case(ESTIMATION_CASE, _ok(INSUFFICIENT))["passed"] is False
    edge_case = {**ESTIMATION_CASE, "allow_abstention": True}
    assert evaluate_case(edge_case, _ok(INSUFFICIENT))["passed"] is True


def test_estimate_without_sources_is_not_grounded():
    assert evaluate_case(ESTIMATION_CASE, _ok(_estimate(60, sources=0)))["grounded"] is False


def test_abstention_case_passes_when_system_abstains():
    result = evaluate_case(ABSTENTION_CASE, _ok(INSUFFICIENT))
    assert (result["type"], result["passed"]) == ("abstention", True)


def test_abstention_case_fails_when_system_invents_a_number():
    assert evaluate_case(ABSTENTION_CASE, _ok(_estimate(45, confidence="low")))["passed"] is False


@pytest.mark.parametrize("case", [ESTIMATION_CASE, ABSTENTION_CASE])
def test_http_error_never_passes(case):
    result = evaluate_case(case, {"status": 502, "body": {"detail": "x"}, "latency_ms": 5.0, "error": "HTTP 502"})
    assert result["passed"] is False
    assert result["error"] == "HTTP 502"


def test_summarize_computes_report_metrics():
    evaluations = [
        {**evaluate_case(ESTIMATION_CASE, _ok(_estimate(60))), "latency_ms": 1000.0},   # pass, err 0
        {**evaluate_case(ESTIMATION_CASE, _ok(_estimate(140))), "latency_ms": 3000.0},  # fail, err 80
        {**evaluate_case(ABSTENTION_CASE, _ok(INSUFFICIENT)), "latency_ms": 200.0},     # pass
        {**evaluate_case(ESTIMATION_CASE, {"status": 502, "body": {}, "latency_ms": 0.0, "error": "HTTP 502"}),
         "latency_ms": 800.0},                                                           # fail, error
    ]
    metrics = summarize(evaluations)
    assert metrics["within_range_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert metrics["mean_absolute_error"] == 40
    assert metrics["abstention_correct"] is True
    assert metrics["mean_latency_ms"] == 1250.0
    assert metrics["p95_latency_ms"] == 3000.0
    assert metrics["error_rate"] == 0.25
    assert metrics["grounded_rate"] == 1.0
    assert (metrics["n_cases"], metrics["n_passed"]) == (4, 2)


def test_summarize_without_abstention_cases_reports_none():
    evaluations = [{**evaluate_case(ESTIMATION_CASE, _ok(_estimate(60))), "latency_ms": 10.0}]
    assert summarize(evaluations)["abstention_correct"] is None


def test_golden_set_contract():
    cases = load_golden_set(DEFAULT_GOLDEN_SET)
    assert len(cases) >= 5
    assert len({c["id"] for c in cases}) == len(cases), "case ids must be unique"
    assert any(c.get("expect_abstention") for c in cases), "at least one abstention case"
    for case in cases:
        assert len(case["transcript"]) >= 100, f"{case['id']}: endpoint requires >= 100 chars"
        if case.get("expect_abstention"):
            assert case["expected_engineer_days"] is None and case["acceptable_range"] is None
        else:
            low, high = case["acceptable_range"]
            assert low <= case["expected_engineer_days"] <= high, case["id"]
