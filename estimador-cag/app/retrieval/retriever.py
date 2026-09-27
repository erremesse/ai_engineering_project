"""Retriever de RAG: vectorial (Sesion 09) + hibrido/rerank (Sesion 10).

A diferencia de `embedding_pipeline.router.search` (Sesion 08, sin tocar), este
retriever aplica un umbral de distancia y filtros estructurales, y adopta soft-fail:
si nada supera el threshold, devuelve una lista vacia con `low_confidence=True` en
vez de dejar que el orquestador alimente al generador con un contexto vacio. Esa
senal sale siempre de la rama vectorial (es un concepto de distancia coseno que
`ts_rank` no tiene un analogo directo de), independientemente de `search_mode`.

`search_mode="hybrid"` anade una rama lexica (`ChunkStore.search_fulltext`) y
fusiona ambas con Reciprocal Rank Fusion (`app.retrieval.fusion`). `rerank=True`
aplica el patron recall-then-rerank: se recupera un pool amplio
(`recall_pool_size`, tipicamente 50) de una o ambas ramas, y el cross-encoder
(`app.retrieval.reranker`) se queda con los `top_k` mejores. Las cuatro
configuraciones evaluadas en `scripts/measure_retrieval.py` son exactamente las
cuatro combinaciones de `search_mode`/`rerank` de esta misma funcion.
"""

import asyncio
from typing import Literal

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.embedding_pipeline.embedder import get_embedder
from app.embedding_pipeline.store import ChunkStore
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranker import get_reranker
from app.retrieval.schemas import RetrievalResult, RetrievedChunk

_store = ChunkStore()


def _to_chunk(row: Row) -> RetrievedChunk:
    distance = getattr(row, "distance", None)
    return RetrievedChunk(
        id=row.id,
        content=row.content,
        sector=row.metadata_.get("client_sector"),
        project_year=row.metadata_.get("year"),
        chunk_type=row.chunk_type,
        distance=float(distance) if distance is not None else None,
        budget_id=row.metadata_.get("budget_id"),
    )


async def search_chunks(
    session: AsyncSession,
    *,
    query_text: str,
    top_k: int,
    distance_threshold: float,
    sectors: list[str] | None = None,
    project_year_min: int | None = None,
    project_year_max: int | None = None,
    chunk_types: list[str] | None = None,
    tech_stack: list[str] | None = None,
    search_mode: Literal["vector", "hybrid"] = "vector",
    rerank: bool = False,
    recall_pool_size: int = 50,
    rrf_k: int = 60,
) -> RetrievalResult:
    fetch_k = recall_pool_size if (search_mode == "hybrid" or rerank) else top_k
    filters = dict(
        sectors=sectors,
        project_year_min=project_year_min,
        project_year_max=project_year_max,
        chunk_types=chunk_types,
        tech_stack=tech_stack,
    )

    embedder = get_embedder()
    query_vector = await run_in_threadpool(embedder.embed_one, query_text)

    if search_mode == "hybrid":
        vector_rows, lexical_rows = await asyncio.gather(
            _store.search_filtered(
                session, query_vector=query_vector, top_k=fetch_k, distance_threshold=distance_threshold, **filters
            ),
            _store.search_fulltext(session, query_text=query_text, top_k=fetch_k, **filters),
        )
        fused_ids = reciprocal_rank_fusion(
            [[row.id for row in vector_rows], [row.id for row in lexical_rows]],
            k=rrf_k,
        )
        rows_by_id = {row.id: row for row in [*vector_rows, *lexical_rows]}
        candidate_rows = [rows_by_id[chunk_id] for chunk_id in fused_ids]
    else:
        vector_rows = await _store.search_filtered(
            session, query_vector=query_vector, top_k=fetch_k, distance_threshold=distance_threshold, **filters
        )
        candidate_rows = vector_rows

    low_confidence = len(vector_rows) == 0
    candidates = [_to_chunk(row) for row in candidate_rows]

    if rerank:
        candidates = await run_in_threadpool(get_reranker().rerank, query_text, candidates, top_k)
    else:
        candidates = candidates[:top_k]

    return RetrievalResult(
        chunks=candidates,
        low_confidence=low_confidence,
        candidates_evaluated=fetch_k,
    )
