#!/usr/bin/env python3
"""Artisanal retrieval measurement against a hand-annotated golden set (Sesion 10).

Runs the four configurations required by the exercise — vector/hybrid search
crossed with reranking on/off — against `golden_set.json`, computing
precision@5 (at the budget_id level, counted exactly as the query returns it —
see the note below) and query latency for each. This calls `search_chunks(...)`
directly, in-process, skipping the transcript-reformulation stage: the golden
set queries are already clean text, so this measures retrieval alone, not the
reformulator, and avoids paying LLM cost on every run.

Precision counts each retrieved chunk's budget_id independently, without
deduplicating repeats within the same top-K. If the same historical budget
dominates the top-5 with several of its components, a relevant match there
counts once per occurrence — this mirrors the diagnostic from Session 09
(`arquitectura-actual.md`, fallo #4: "4 of 5 results from the same budget") and
is left visible rather than silently corrected, because it is informative:
a config that scores well by returning five components of one good match is
answering a different question than one that surfaces five distinct relevant
budgets.

Usage:

    docker compose up -d
    docker compose run --rm ai_service python scripts/measure_retrieval.py
"""

import asyncio
import json
import time
from pathlib import Path
from statistics import median

from app.config import get_settings
from app.db.session import get_session_factory
from app.retrieval.retriever import search_chunks

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
TOP_K = 5
RUNS_PER_QUERY = 3

CONFIGS = [
    {"label": "A", "name": "Vector / No rerank", "search_mode": "vector", "rerank": False},
    {"label": "B", "name": "Hybrid / No rerank", "search_mode": "hybrid", "rerank": False},
    {"label": "C", "name": "Vector / Rerank", "search_mode": "vector", "rerank": True},
    {"label": "D", "name": "Hybrid / Rerank", "search_mode": "hybrid", "rerank": True},
]


def precision_at_k(retrieved_budget_ids: list[str | None], relevant_ids: set[str], k: int) -> float:
    """Fraction of the top-k retrieved chunks whose budget_id is relevant."""
    top = retrieved_budget_ids[:k]
    if not top:
        return 0.0
    hits = sum(1 for budget_id in top if budget_id in relevant_ids)
    return hits / len(top)


async def measure_config(session, config: dict, golden_set: dict, settings) -> dict:
    precisions: list[float] = []
    latencies_ms: list[float] = []

    for entry in golden_set["queries"]:
        relevant_ids = set(entry["relevant_budget_ids"])
        result = None

        for _ in range(RUNS_PER_QUERY):
            start = time.perf_counter()
            result = await search_chunks(
                session,
                query_text=entry["query"],
                top_k=TOP_K,
                distance_threshold=settings.RAG_DISTANCE_THRESHOLD,
                search_mode=config["search_mode"],
                rerank=config["rerank"],
                recall_pool_size=settings.RAG_RECALL_POOL_SIZE,
                rrf_k=settings.RAG_RRF_K,
            )
            latencies_ms.append((time.perf_counter() - start) * 1000)

        retrieved_budget_ids = [chunk.budget_id for chunk in result.chunks]
        precision = precision_at_k(retrieved_budget_ids, relevant_ids, TOP_K)
        precisions.append(precision)
        print(f"  [{config['label']}] {entry['id']}: precision@{TOP_K} = {precision:.2f}")

    return {
        "label": config["label"],
        "name": config["name"],
        "mean_precision": sum(precisions) / len(precisions),
        "median_latency_ms": median(latencies_ms),
    }


async def main() -> int:
    golden_set = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    settings = get_settings()

    rows: list[dict] = []
    async with get_session_factory()() as session:
        for config in CONFIGS:
            print(f"\nConfiguration {config['label']} — {config['name']}")
            rows.append(await measure_config(session, config, golden_set, settings))

    print("\n" + "=" * 60)
    print(f"{'Config':<8}{'Search/Rerank':<24}{'Mean P@5':<12}{'Median latency (ms)':<20}")
    print("-" * 60)
    for row in rows:
        print(f"{row['label']:<8}{row['name']:<24}{row['mean_precision']:<12.2f}{row['median_latency_ms']:<20.0f}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
