#!/usr/bin/env python3
"""Smoke test de busqueda semantica contra el corpus persistido (Sesion 08).

Sustituye a `compare.py` (Sesion 07): en vez de medir similitud entre dos
textos sueltos, ejercita el camino real de retrieval — HTTP contra
`POST /embeddings/ingest` y `POST /search` — con cinco queries que exploran el
corpus desde angulos distintos (match directo, reformulacion semantica,
dominio ajeno, ambigua, muy especifica).

Idempotente: primero ingesta el corpus elegido (un documento por presupuesto);
los documentos ya persistidos responden 409 y se saltan, asi que volver a
ejecutar el script nunca duplica datos.

Uso:

    docker compose up -d
    docker compose exec ai-service python scripts/query_examples.py

    # corpus en espanol (Sesion 10), mismos budget_id que el corpus ingles:
    docker compose exec ai-service python scripts/query_examples.py \
        --corpus data/budgets_sample_es.json

    # o desde el host (cd ai-service), con el override de desarrollo que
    # publica el puerto 8000 (docker-compose.dev.yml):
    uv run python scripts/query_examples.py

La URL base se toma de QUERY_EXAMPLES_BASE_URL si esta definida (deliberadamente
distinta de AI_SERVICE_URL, que usa el business-backend); si no, el script
prueba http://localhost:8000 y http://ai-service:8000 (nombre de servicio en
compose) via GET /health. Desde la Sesion 15 envia X-Service-Token con el valor
de AI_SERVICE_TOKEN, que ya esta en el entorno del contenedor ai-service.

`source_path` (la clave de idempotencia de la ingesta) incluye el nombre del
fichero de corpus, asi que el corpus ingles y el espanol nunca colisionan entre
si aunque compartan `budget_id` — pueden convivir en la misma base de datos si
se ingieren los dos, o usarse uno a la vez tras un TRUNCATE (asi es como se
comparan en `docs/session10-hybrid-rerank-evaluation.md`).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_PATH = ROOT / "data" / "budgets_sample.json"

CANDIDATE_BASE_URLS = ("http://localhost:8000", "http://ai-service:8000")

# Cinco angulos sobre el mismo corpus — ver el enunciado del ejercicio.
QUERIES: list[tuple[str, str]] = [
    (
        "Componente directo conocido (sanity check)",
        "REST API development with JWT authentication for financial sector",
    ),
    (
        "Reformulacion semantica (mismo concepto, otro vocabulario)",
        "secure backend service with token-based access control for banking applications",
    ),
    (
        "Dominio distinto (no deberia estar en el corpus)",
        "mobile application for restaurant reservations",
    ),
    (
        "Consulta ambigua (sin match dominante)",
        "integration with external system",
    ),
    (
        "Consulta muy especifica (vocabulario tecnico preciso)",
        "migration from monolith to microservices architecture using Kubernetes",
    ),
]

TOP_K = 5
CONTENT_PREVIEW_CHARS = 120


def resolve_base_url(client: httpx.Client) -> str:
    """Respeta QUERY_EXAMPLES_BASE_URL; si no, prueba las URLs candidatas."""
    explicit = os.environ.get("QUERY_EXAMPLES_BASE_URL")
    candidates = (explicit,) if explicit else CANDIDATE_BASE_URLS
    for base_url in candidates:
        try:
            if client.get(f"{base_url}/health").status_code == 200:
                return base_url
        except httpx.TransportError:
            continue
    print(
        "ERROR: no se pudo contactar con el servicio IA. Levanta el stack "
        "(docker compose up -d) o define QUERY_EXAMPLES_BASE_URL.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def ingest_corpus(client: httpx.Client, base_url: str, corpus_path: Path) -> None:
    """Un documento por presupuesto; 409 significa que ya estaba (idempotente)."""
    budgets = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus_label = f"data/{corpus_path.name}"
    created, skipped = 0, 0
    for budget in budgets:
        response = client.post(
            f"{base_url}/embeddings/ingest",
            json={
                "source_path": f"{corpus_label}::{budget['budget_id']}",
                "document_type": "historical_budget",
                "content": budget,
            },
        )
        if response.status_code == 200:
            created += 1
        elif response.status_code == 409:
            skipped += 1
        else:
            print(
                f"ERROR ingiriendo {budget['budget_id']}: "
                f"{response.status_code} {response.text[:200]}",
                file=sys.stderr,
            )
            raise SystemExit(1)

    print(f"Corpus ({corpus_label}): {len(budgets)} presupuestos — {created} ingeridos, {skipped} ya presentes.")


def run_queries(client: httpx.Client, base_url: str) -> None:
    for index, (label, query) in enumerate(QUERIES, start=1):
        response = client.post(f"{base_url}/search", json={"query": query, "k": TOP_K})
        response.raise_for_status()
        body = response.json()

        print()
        print(f"[{index}/5] {label}")
        print(f'    query: "{query}"')
        print(f"    search_time_ms: {body['search_time_ms']}")
        print(f"    {'chunk_id':>8}  {'distance':>8}  {'chunk_type':<18}  content")
        for hit in body["results"]:
            preview = " ".join(hit["content"].split())[:CONTENT_PREVIEW_CHARS]
            print(
                f"    {hit['chunk_id']:>8}  {hit['distance']:>8.4f}  "
                f"{hit['chunk_type']:<18}  {preview}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS_PATH,
        help="Ruta al JSON de presupuestos a ingerir (default: data/budgets_sample.json).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("AI_SERVICE_TOKEN")
    headers = {"X-Service-Token": token} if token else {}
    with httpx.Client(timeout=120.0, headers=headers) as client:
        base_url = resolve_base_url(client)
        print(f"Servicio IA: {base_url}")
        ingest_corpus(client, base_url, args.corpus)
        run_queries(client, base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
