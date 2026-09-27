"""Evaluation harness (Sesion 16): golden set -> servicio IA desplegado -> metricas.

Lanza cada caso de `eval/golden_set.json` contra POST /v1/estimate/from-transcript
del servicio real (no un mock: consume tokens del LLM) y compara la respuesta con lo
esperado:

- caso de estimacion: pasa si `total_engineer_days` cae dentro de `acceptable_range`;
- caso de abstencion: pasa si el sistema reconoce que no sabe
  (`confidence == "insufficient"` o `total_engineer_days is None`).

No confundir con `scripts/golden_set.json` (Sesion 10), que solo mide el retrieval
(precision@k por budget_id) en proceso y sin LLM. Ver eval/README.md.

Uso (desde ai-service/, con el servicio publicado en :8000 por docker-compose.dev.yml):

    AI_SERVICE_TOKEN=... uv run python eval/run_eval.py
    uv run python eval/run_eval.py --only case-001 --only case-007

Variables de entorno: AI_SERVICE_URL (por defecto http://localhost:8000),
AI_SERVICE_TOKEN y, si el servicio la exige, ESTIMATE_API_KEY. Nunca se escriben
en el informe.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
DEFAULT_GOLDEN_SET = EVAL_DIR / "golden_set.json"
DEFAULT_REPORTS_DIR = EVAL_DIR / "reports"
ESTIMATE_PATH = "/v1/estimate/from-transcript"
# The generation step alone takes ~80 s with claude-sonnet-5 (docs/example_run_compose.txt);
# the 30 s of the session sketch would turn every case into a timeout.
DEFAULT_TIMEOUT_S = 240.0

AI_SERVICE_URL = os.environ.get("AI_SERVICE_URL", "http://localhost:8000").rstrip("/")
SERVICE_TOKEN = os.environ.get("AI_SERVICE_TOKEN", "")
ESTIMATE_API_KEY = os.environ.get("ESTIMATE_API_KEY", "")


def load_golden_set(path: Path) -> list[dict]:
    """Carga los casos y resuelve `transcript_file` (ruta relativa a la raiz del repo)."""
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    for case in cases:
        if "transcript" not in case:
            case["transcript"] = (REPO_ROOT / case["transcript_file"]).read_text(encoding="utf-8")
    return cases


def _headers() -> dict:
    headers = {"X-Service-Token": SERVICE_TOKEN}
    if ESTIMATE_API_KEY:
        headers["X-API-Key"] = ESTIMATE_API_KEY
    return headers


def call_estimate(case: dict, client: httpx.Client) -> dict:
    """Una llamada real al servicio. Nunca lanza: los fallos quedan en `error`."""
    started = time.perf_counter()
    try:
        response = client.post(
            ESTIMATE_PATH,
            headers=_headers(),
            json={"transcript": case["transcript"], "idempotency_key": f"eval-{case['id']}"},
        )
        status, error = response.status_code, None
        try:
            body = response.json()
        except ValueError:
            body, error = {}, "invalid JSON response"
        if status != 200:
            error = f"HTTP {status}: {body.get('detail', '') if isinstance(body, dict) else ''}".strip()
    except httpx.HTTPError as exc:
        status, body, error = None, {}, f"{type(exc).__name__}: {exc}"
    latency_ms = (time.perf_counter() - started) * 1000
    return {"status": status, "body": body, "latency_ms": latency_ms, "error": error}


def _abstained(body: dict) -> bool:
    return body.get("confidence") == "insufficient" or body.get("total_engineer_days") is None


def evaluate_case(case: dict, result: dict) -> dict:
    """Compara una respuesta con lo esperado. Aqui se codifica la definicion de "bueno"."""
    body = result["body"] if result["status"] == 200 else {}
    predicted = body.get("total_engineer_days")
    evaluation = {
        "id": case["id"],
        "difficulty": case.get("difficulty"),
        "status": result["status"],
        "error": result["error"],
        "confidence": body.get("confidence"),
        "predicted": predicted,
        "n_sources": len(body.get("sources", [])),
    }

    if result["status"] != 200:
        # An error is never a correct answer — not even for an abstention case.
        kind = "abstention" if case.get("expect_abstention") else "estimation"
        return {**evaluation, "type": kind, "passed": False, "abs_error": None}

    # Abstention case: the system must recognise it has no data.
    if case.get("expect_abstention"):
        return {**evaluation, "type": "abstention", "passed": _abstained(body), "abs_error": None}

    # Estimation case: the estimate must fall within the acceptable range.
    low, high = case["acceptable_range"]
    abstained = _abstained(body)
    within_range = predicted is not None and low <= predicted <= high
    abs_error = abs(predicted - case["expected_engineer_days"]) if predicted is not None else None
    return {
        **evaluation,
        "type": "estimation",
        "passed": within_range or (abstained and case.get("allow_abstention", False)),
        "abstained": abstained,
        "expected": case["expected_engineer_days"],
        "acceptable_range": [low, high],
        "abs_error": abs_error,
        # Grounded = a numeric estimate that cites at least one historical source.
        "grounded": predicted is not None and evaluation["n_sources"] > 0,
    }


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def summarize(evaluations: list[dict]) -> dict:
    """Agrega las evaluaciones por caso en las metricas del informe."""
    estimation_cases = [e for e in evaluations if e["type"] == "estimation"]
    abstention_cases = [e for e in evaluations if e["type"] == "abstention"]
    within_range = [e for e in estimation_cases if e["passed"]]
    errors = [e["abs_error"] for e in estimation_cases if e["abs_error"] is not None]
    numeric = [e for e in estimation_cases if e["predicted"] is not None]
    latencies = [e["latency_ms"] for e in evaluations]

    def ratio(part: list, whole: list) -> float | None:
        return round(len(part) / len(whole), 3) if whole else None

    return {
        "within_range_rate": ratio(within_range, estimation_cases),
        "mean_absolute_error": round(sum(errors) / len(errors), 2) if errors else None,
        "abstention_correct": all(e["passed"] for e in abstention_cases) if abstention_cases else None,
        "abstention_rate": ratio([e for e in abstention_cases if e["passed"]], abstention_cases),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "p95_latency_ms": round(_p95(latencies), 1) if latencies else None,
        "error_rate": ratio([e for e in evaluations if e["status"] != 200], evaluations),
        "grounded_rate": ratio([e for e in numeric if e["grounded"]], numeric),
        "n_cases": len(evaluations),
        "n_passed": sum(e["passed"] for e in evaluations),
    }


def run(golden_set_path: Path = DEFAULT_GOLDEN_SET, only: list[str] | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    cases = load_golden_set(golden_set_path)
    if only:
        cases = [c for c in cases if c["id"] in only]

    evaluations = []
    with httpx.Client(base_url=AI_SERVICE_URL, timeout=timeout_s) as client:
        for case in cases:
            print(f"[{case['id']}] {case.get('difficulty', '')} ...", end=" ", flush=True, file=sys.stderr)
            result = call_estimate(case, client)
            evaluation = evaluate_case(case, result)
            evaluation["latency_ms"] = round(result["latency_ms"], 1)
            evaluations.append(evaluation)
            verdict = "PASS" if evaluation["passed"] else "FAIL"
            print(f"{verdict} predicted={evaluation['predicted']} confidence={evaluation['confidence']} "
                  f"({evaluation['latency_ms'] / 1000:.1f}s){' ' + evaluation['error'] if evaluation['error'] else ''}",
                  file=sys.stderr)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ai_service_url": AI_SERVICE_URL,
        "model": os.environ.get("ANTHROPIC_MODEL") or os.environ.get("EVAL_MODEL_LABEL"),
        "golden_set": str(Path(golden_set_path).resolve().relative_to(REPO_ROOT)).replace("\\", "/"),
        "golden_set_sha256": hashlib.sha256(Path(golden_set_path).read_bytes()).hexdigest()[:12],
        "metrics": summarize(evaluations),
        "cases": evaluations,
    }


def save_report(report: dict, reports_dir: Path = DEFAULT_REPORTS_DIR) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = reports_dir / f"eval-{stamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the golden set against the deployed AI service.")
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--only", action="append", help="Run only this case id (repeatable).")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="Per-request timeout (s).")
    args = parser.parse_args()

    if not SERVICE_TOKEN:
        print("WARNING: AI_SERVICE_TOKEN is empty; the service will answer 401 unless its guard is off.",
              file=sys.stderr)

    report = run(args.golden_set, only=args.only, timeout_s=args.timeout)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Report saved to {save_report(report, args.reports_dir)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
