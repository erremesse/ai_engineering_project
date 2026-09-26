"""Retriever de RAG: top-K + distance_threshold + filtros de metadata sobre pgvector.

A diferencia de `embedding_pipeline.router.search` (Sesion 08, sin tocar), este
retriever aplica un umbral de distancia y filtros estructurales, y adopta soft-fail:
si nada supera el threshold, devuelve una lista vacia con `low_confidence=True` en
vez de dejar que el orquestador alimente al generador con un contexto vacio.
"""

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.embedding_pipeline.embedder import get_embedder
from app.embedding_pipeline.store import ChunkStore
from app.retrieval.schemas import RetrievalResult, RetrievedChunk

_store = ChunkStore()


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
) -> RetrievalResult:
    embedder = get_embedder()
    query_vector = await run_in_threadpool(embedder.embed_one, query_text)

    rows = await _store.search_filtered(
        session,
        query_vector=query_vector,
        top_k=top_k,
        distance_threshold=distance_threshold,
        sectors=sectors,
        project_year_min=project_year_min,
        project_year_max=project_year_max,
        chunk_types=chunk_types,
        tech_stack=tech_stack,
    )

    chunks = [
        RetrievedChunk(
            id=row.id,
            content=row.content,
            sector=row.metadata_.get("client_sector"),
            project_year=row.metadata_.get("year"),
            chunk_type=row.chunk_type,
            distance=float(row.distance),
        )
        for row in rows
    ]

    return RetrievalResult(
        chunks=chunks,
        low_confidence=len(chunks) == 0,
        # top_k pedido, no el recuento exacto de candidatos antes del threshold
        # (habria que una COUNT(*) adicional sin LIMIT para eso).
        candidates_evaluated=top_k,
    )
