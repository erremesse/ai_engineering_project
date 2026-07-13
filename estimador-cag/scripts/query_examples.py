#!/usr/bin/env python3
"""Smoke test de busqueda semantica contra el corpus persistido (Sesion 08).

Sustituye a `compare.py` (Sesion 07): en vez de medir similitud entre dos
textos sueltos, ejercita el camino real de retrieval — HTTP contra
`POST /embeddings/ingest` y `POST /search` — con cinco queries que exploran el
corpus desde angulos distintos (match directo, reformulacion semantica,
dominio ajeno, ambigua, muy especifica).

Idempotente: primero ingesta `data/budgets_sample.json` (un documento por
presupuesto); los documentos ya persistidos responden 409 y se saltan, asi que
volver a ejecutar el script nunca duplica datos.

Uso:

    docker compose up -d
    docker compose run --rm ai_service python scripts/query_examples.py

    # o desde el host, con la API en localhost:8000:
    uv run python scripts/query_examples.py

La URL base se toma de QUERY_EXAMPLES_BASE_URL si esta definida (deliberadamente
distinta de ESTIMADOR_API_BASE, que usa Streamlit desde la perspectiva del host:
dentro del contenedor ese valor sigue apuntando a localhost y nunca resolveria);
si no, el script prueba http://localhost:8000 y http://ai_service:8000 (alias de
red de compose) via GET /health.
"""

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
CORPUS_PATH = ROOT / "data" / "budgets_sample.json"

CANDIDATE_BASE_URLS = ("http://localhost:8000", "http://ai_service:8000")

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
        "(docker compose up -d) o define ESTIMADOR_API_BASE.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def ingest_corpus(client: httpx.Client, base_url: str) -> None:
    """Un documento por presupuesto; 409 significa que ya estaba (idempotente)."""
    budgets = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    created, skipped = 0, 0
    for budget in budgets:
        response = client.post(
            f"{base_url}/embeddings/ingest",
            json={
                "source_path": f"data/budgets_sample.json::{budget['budget_id']}",
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

    print(f"Corpus: {len(budgets)} presupuestos — {created} ingeridos, {skipped} ya presentes.")


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


def main() -> int:
    with httpx.Client(timeout=120.0) as client:
        base_url = resolve_base_url(client)
        print(f"Servicio IA: {base_url}")
        ingest_corpus(client, base_url)
        run_queries(client, base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
