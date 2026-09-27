"""Dashboard basico de monitorizacion (Sesion 16).

Lee el JSONL de metricas que escribe el servicio IA (`app/observability.py`, una
linea `estimate_request` por peticion de estimacion) y genera un HTML autocontenido
(SVG inline, sin dependencias ni CDN) con las tres senales clave de produccion:

- latencia por peticion (media y p95);
- coste por peticion (derivado del recuento de tokens);
- tasa de error (proporcion de respuestas no 200).

Uso (desde ai-service/):

    docker compose cp ai-service:/app/metrics/estimate_requests.jsonl eval/metrics/
    uv run python eval/dashboard.py                      # -> eval/dashboard/dashboard.html
    uv run python eval/dashboard.py --since 2026-09-27T00:00 --endpoint /v1/estimate/from-transcript

El golden set (run_eval.py) mide la calidad cuando lo lanzamos; este panel vigila lo
que pasa en produccion todo el rato. El /health no llama al modelo a proposito: la
salud del modelo se ve aqui, no en el healthcheck.
"""

import argparse
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = EVAL_DIR / "metrics" / "estimate_requests.jsonl"
DEFAULT_OUTPUT = EVAL_DIR / "dashboard" / "dashboard.html"


# --------------------------------------------------------------------------- data

def load_records(path: Path, since: str | None = None, endpoint: str | None = None) -> list[dict]:
    records = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if since and record["ts"] < since:
            continue
        if endpoint and record["endpoint"] != endpoint:
            continue
        records.append(record)
    return sorted(records, key=lambda r: r["ts"])


def p95(values: list[float]) -> float | None:
    """Nearest-rank p95: the value 95% of requests stay at or below."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def error_rate(records: list[dict]) -> float | None:
    if not records:
        return None
    return sum(r["status_code"] != 200 for r in records) / len(records)


def summarize(records: list[dict]) -> dict:
    latencies = [r["latency_ms"] for r in records]
    costs = [r["estimated_cost_usd"] for r in records]
    ok = [r for r in records if r["status_code"] == 200]
    return {
        "requests": len(records),
        "error_rate": error_rate(records),
        "mean_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "p95_latency_ms": p95(latencies),
        # Cost per successful estimate is what the business pays per answer.
        "mean_cost_usd": sum(r["estimated_cost_usd"] for r in ok) / len(ok) if ok else None,
        "total_cost_usd": sum(costs),
        "prompt_tokens": sum(r["prompt_tokens"] for r in records),
        "completion_tokens": sum(r["completion_tokens"] for r in records),
    }


def per_endpoint(records: list[dict]) -> list[tuple[str, dict]]:
    endpoints = sorted({r["endpoint"] for r in records})
    return [(e, summarize([r for r in records if r["endpoint"] == e])) for e in endpoints]


def status_counts(records: list[dict]) -> list[tuple[int, int]]:
    counts: dict[int, int] = {}
    for r in records:
        counts[r["status_code"]] = counts.get(r["status_code"], 0) + 1
    return sorted(counts.items())


# ------------------------------------------------------------------ formatting

def fmt_seconds(ms: float | None) -> str:
    return "—" if ms is None else f"{ms / 1000:.1f} s"


def fmt_usd(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:.4f}" if value < 0.1 else f"${value:.2f}"


def fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def nice_ticks(max_value: float, count: int = 4) -> list[float]:
    if max_value <= 0:
        return [0.0, 1.0]
    raw = max_value / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    return [step * i for i in range(math.ceil(max_value / step) + 1)]


def _tick_label(value: float, unit: str) -> str:
    if unit == "usd":
        return f"${value:.3f}".rstrip("0").rstrip(".") if value else "$0"
    return f"{value:g}"


STATUS_CLASS = {2: ("good", "OK"), 4: ("warning", "Rechazo del cliente"), 5: ("critical", "Error del servicio")}


# ---------------------------------------------------------------------- charts

W, H = 640, 240
PAD_L, PAD_R, PAD_T, PAD_B = 52, 64, 16, 32


def _frame(ticks: list[float], unit: str, x_label: str) -> tuple[list[str], callable]:
    top = ticks[-1]
    plot_h = H - PAD_T - PAD_B

    def y(v: float) -> float:
        return PAD_T + plot_h * (1 - v / top)

    parts = []
    for t in ticks:
        parts.append(f'<line class="grid" x1="{PAD_L}" x2="{W - PAD_R}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        parts.append(f'<text class="tick" x="{PAD_L - 8}" y="{y(t) + 4:.1f}" text-anchor="end">'
                     f'{_tick_label(t, unit)}</text>')
    parts.append(f'<line class="axis" x1="{PAD_L}" x2="{W - PAD_R}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    parts.append(f'<text class="tick" x="{(PAD_L + W - PAD_R) / 2}" y="{H - 6}" text-anchor="middle">{x_label}</text>')
    return parts, y


def _x_positions(n: int) -> list[float]:
    plot_w = W - PAD_L - PAD_R
    band = plot_w / max(n, 1)
    return [PAD_L + band * (i + 0.5) for i in range(n)]


def latency_chart(records: list[dict], p95_ms: float | None) -> str:
    seconds = [r["latency_ms"] / 1000 for r in records]
    ticks = nice_ticks(max(seconds + [(p95_ms or 0) / 1000]))
    parts, y = _frame(ticks, "s", "peticiones, en orden cronológico")
    xs = _x_positions(len(records))
    if len(xs) > 1:
        points = " ".join(f"{x:.1f},{y(s):.1f}" for x, s in zip(xs, seconds))
        parts.append(f'<polyline class="series-line" points="{points}"/>')
    if p95_ms is not None:
        yp = y(p95_ms / 1000)
        parts.append(f'<line class="ref" x1="{PAD_L}" x2="{W - PAD_R}" y1="{yp:.1f}" y2="{yp:.1f}"/>')
        parts.append(f'<text class="ref-label" x="{W - PAD_R + 6}" y="{yp + 4:.1f}">p95 {p95_ms / 1000:.1f} s</text>')
    for x, s, r in zip(xs, seconds, records):
        tip = f"{r['ts']} · {r['endpoint']} · HTTP {r['status_code']} · {s:.1f} s"
        dot_class = "dot" if r["status_code"] == 200 else "dot dot-error"
        parts.append(f'<g class="hit"><title>{html.escape(tip)}</title>'
                     f'<circle cx="{x:.1f}" cy="{y(s):.1f}" r="12" class="hit-area"/>'
                     f'<circle cx="{x:.1f}" cy="{y(s):.1f}" r="4" class="{dot_class}"/></g>')
    return _svg("Latencia por petición, en segundos, con la línea del p95", parts)


def cost_chart(records: list[dict]) -> str:
    costs = [r["estimated_cost_usd"] for r in records]
    ticks = nice_ticks(max(costs) if costs else 0)
    parts, y = _frame(ticks, "usd", "peticiones, en orden cronológico")
    xs = _x_positions(len(records))
    band = (W - PAD_L - PAD_R) / max(len(records), 1)
    bar_w = min(24.0, band - 2)  # capped thickness, >= 2px surface gap between bars
    base = y(0)
    for x, c, r in zip(xs, costs, records):
        top = y(c)
        h = base - top
        rad = min(4.0, h / 2, bar_w / 2)
        x0, x1 = x - bar_w / 2, x + bar_w / 2
        # Rounded data-end, square at the baseline.
        d = (f"M{x0:.1f},{base:.1f} V{top + rad:.1f} Q{x0:.1f},{top:.1f} {x0 + rad:.1f},{top:.1f} "
             f"H{x1 - rad:.1f} Q{x1:.1f},{top:.1f} {x1:.1f},{top + rad:.1f} V{base:.1f} Z")
        tip = (f"{r['ts']} · {r['endpoint']} · {fmt_usd(c)} "
               f"({r['prompt_tokens']:,} tokens de entrada / {r['completion_tokens']:,} de salida)")
        parts.append(f'<g class="hit"><title>{html.escape(tip)}</title>'
                     f'<rect x="{x - band / 2:.1f}" y="{PAD_T}" width="{band:.1f}" height="{base - PAD_T:.1f}" class="hit-area"/>'
                     f'<path d="{d}" class="bar"/></g>')
    return _svg("Coste estimado por petición, en USD", parts)


def status_chart(records: list[dict]) -> str:
    counts = status_counts(records)
    total = sum(c for _, c in counts) or 1
    # Full-width card: a wider viewBox keeps the text at the same size as the other charts.
    width, row_h, bar_h, label_w = 1040, 32, 16, 230
    height = max(row_h * len(counts) + 8, 44)
    track_w = width - label_w - 90
    parts = []
    for i, (code, n) in enumerate(counts):
        kind, meaning = STATUS_CLASS.get(code // 100, ("serious", "Otro"))
        y0 = 8 + i * row_h
        w = max(track_w * n / total, 4)
        icon = "✓" if kind == "good" else "!"
        parts.append(f'<text class="label" x="0" y="{y0 + 12}"><tspan class="status-icon {kind}">{icon}</tspan> '
                     f'HTTP {code} · {meaning}</text>')
        parts.append(f'<g class="hit"><title>HTTP {code}: {n} de {total} peticiones</title>'
                     f'<rect x="{label_w}" y="{y0}" width="{w:.1f}" height="{bar_h}" rx="4" class="status {kind}"/></g>')
        parts.append(f'<text class="value" x="{label_w + w + 8:.1f}" y="{y0 + 12}">{n} ({n / total:.0%})</text>')
    return (f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Respuestas por código HTTP">'
            + "".join(parts) + "</svg>")


def _svg(label: str, parts: list[str]) -> str:
    return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(label)}">' + "".join(parts) + "</svg>"


# ------------------------------------------------------------------------ page

CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10); --series-1: #2a78d6;
  --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --series-1: #3987e5;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --series-1: #3987e5;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1080px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 0 0 2px; }
.sub, .note { color: var(--ink-2); margin: 0; }
.note { font-size: 13px; margin-top: 6px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 20px 0; }
.tile, .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.tile .label { color: var(--ink-2); font-size: 13px; }
.tile .value { font-size: 26px; font-weight: 600; margin-top: 2px; }
.tile .hint { color: var(--muted); font-size: 12px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 12px; }
@media (max-width: 480px) { .grid2 { grid-template-columns: 1fr; } }
.card { margin-bottom: 12px; }
svg { width: 100%; height: auto; display: block; margin-top: 10px; overflow: visible; }
svg text { font: 12px system-ui, -apple-system, "Segoe UI", sans-serif; }
.grid { stroke: var(--grid); stroke-width: 1; }
.axis { stroke: var(--axis); stroke-width: 1; }
.tick { fill: var(--muted); font-variant-numeric: tabular-nums; }
.label, .value { fill: var(--ink-2); }
.series-line { fill: none; stroke: var(--series-1); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.dot { fill: var(--series-1); stroke: var(--surface); stroke-width: 2; }
.dot-error { fill: var(--critical); }
.ref { stroke: var(--ink-2); stroke-width: 1; }
.ref-label { fill: var(--ink-2); }
.bar { fill: var(--series-1); }
.hit-area { fill: transparent; }
.hit:hover .dot { r: 6; }
.hit:hover .bar, .hit:hover .status { opacity: 0.8; }
.status.good { fill: var(--good); } .status.warning { fill: var(--warning); }
.status.serious { fill: var(--serious); } .status.critical { fill: var(--critical); }
.status-icon { font-weight: 700; }
.status-icon.good { fill: var(--good); } .status-icon.warning { fill: var(--ink-2); }
.status-icon.critical { fill: var(--critical); } .status-icon.serious { fill: var(--ink-2); }
table { width: 100%; border-collapse: collapse; margin-top: 10px; font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 6px 8px; border-bottom: 1px solid var(--grid); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--ink-2); font-weight: 600; }
.table-wrap { overflow-x: auto; }
details summary { cursor: pointer; color: var(--ink-2); margin-top: 8px; }
"""


def _short_ts(ts: str) -> str:
    """2026-09-27T18:11:39+00:00 -> 27/09 18:11"""
    return f"{ts[8:10]}/{ts[5:7]} {ts[11:16]}"


def _tile(label: str, value: str, hint: str = "") -> str:
    return (f'<div class="tile"><div class="label">{label}</div><div class="value">{value}</div>'
            f'<div class="hint">{hint}</div></div>')


def _endpoint_table(rows: list[tuple[str, dict]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(e)}</td><td>{s['requests']}</td><td>{fmt_pct(s['error_rate'])}</td>"
        f"<td>{fmt_seconds(s['mean_latency_ms'])}</td><td>{fmt_seconds(s['p95_latency_ms'])}</td>"
        f"<td>{fmt_usd(s['mean_cost_usd'])}</td><td>{fmt_usd(s['total_cost_usd'])}</td></tr>"
        for e, s in rows
    )
    return ('<div class="table-wrap"><table><thead><tr><th>Endpoint</th><th>Peticiones</th><th>Errores</th>'
            '<th>Latencia media</th><th>p95</th><th>Coste medio</th><th>Coste total</th></tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def _request_table(records: list[dict]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(r['ts'])}</td><td>{html.escape(r['endpoint'])}</td><td>{r['status_code']}</td>"
        f"<td>{fmt_seconds(r['latency_ms'])}</td><td>{r['prompt_tokens']:,}</td>"
        f"<td>{r['completion_tokens']:,}</td><td>{fmt_usd(r['estimated_cost_usd'])}</td></tr>"
        for r in records
    )
    return ('<details><summary>Ver todas las peticiones en tabla</summary><div class="table-wrap"><table><thead><tr>'
            '<th>Fecha (UTC)</th><th>Endpoint</th><th>HTTP</th><th>Latencia</th><th>Tokens entrada</th>'
            f'<th>Tokens salida</th><th>Coste</th></tr></thead><tbody>{body}</tbody></table></div></details>')


def render_html(records: list[dict], source: str) -> str:
    s = summarize(records)
    window = f"{_short_ts(records[0]['ts'])} → {_short_ts(records[-1]['ts'])} UTC" if records else "sin datos"
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tiles = "".join([
        _tile("Peticiones", f"{s['requests']:,}", window),
        _tile("Tasa de error", fmt_pct(s["error_rate"]), "respuestas no 200"),
        _tile("Latencia media", fmt_seconds(s["mean_latency_ms"]), "todas las peticiones"),
        _tile("Latencia p95", fmt_seconds(s["p95_latency_ms"]), "el 95% de las peticiones tarda menos"),
        _tile("Coste por estimación", fmt_usd(s["mean_cost_usd"]), "media de las respuestas 200"),
        _tile("Coste total", fmt_usd(s["total_cost_usd"]),
              f"{s['prompt_tokens']:,} tokens de entrada / {s['completion_tokens']:,} de salida"),
    ])
    charts = ""
    if records:
        charts = (
            '<div class="grid2">'
            f'<section class="card"><h2>Latencia por petición (s)</h2><p class="note">La línea horizontal marca el p95. '
            f'Los puntos rojos son respuestas no 200.</p>{latency_chart(records, s["p95_latency_ms"])}</section>'
            f'<section class="card"><h2>Coste por petición (USD)</h2><p class="note">Coste derivado del recuento de tokens '
            f'y del precio configurado (LLM_PRICE_*).</p>{cost_chart(records)}</section>'
            "</div>"
            f'<section class="card"><h2>Respuestas por código HTTP</h2>{status_chart(records)}</section>'
            f'<section class="card"><h2>Por endpoint</h2>{_endpoint_table(per_endpoint(records))}'
            f"{_request_table(records)}</section>"
        )
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitor servicio IA</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <h1>Servicio IA: monitor de producción</h1>
  <p class="sub">Endpoints de estimación · origen: {html.escape(source)} · generado {generated}</p>
  <div class="tiles">{tiles}</div>
  {charts or '<p class="sub">No hay peticiones en el intervalo seleccionado.</p>'}
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the production monitoring dashboard.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Metrics JSONL file.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--since", help="ISO timestamp (UTC); older requests are ignored.")
    parser.add_argument("--endpoint", help="Only this endpoint label, e.g. /v1/estimate/from-transcript.")
    args = parser.parse_args()

    records = load_records(args.input, since=args.since, endpoint=args.endpoint)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(records, args.input.name), encoding="utf-8")
    summary = summarize(records)
    print(json.dumps(summary, indent=2))
    print(f"Dashboard written to {args.output}")


if __name__ == "__main__":
    main()
