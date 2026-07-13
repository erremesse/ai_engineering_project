import time

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.embedder import get_embedder
from app.embedding_pipeline.schemas import (
    IngestRequest,
    IngestResponse,
    IngestStats,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from app.embedding_pipeline.store import ChunkStore

router = APIRouter()

logger = structlog.get_logger()

_chunker = JSONStructuralChunker()
_store = ChunkStore()


@router.post(
    "/embeddings/ingest",
    response_model=IngestResponse,
    tags=["embeddings"],
    responses={409: {"description": "Document already ingested"}},
)
async def ingest(
    request: IngestRequest, session: AsyncSession = Depends(get_session)
) -> IngestResponse | JSONResponse:
    started = time.perf_counter()

    async with session.begin():
        existing_id = await _store.find_document_id(session, request.source_path)
        if existing_id is not None:
            logger.info(
                "embedding_ingest_duplicate",
                source_path=request.source_path,
                document_id=existing_id,
            )
            return JSONResponse(
                status_code=409,
                content={"detail": "Document already ingested", "document_id": existing_id},
            )

        chunks = _chunker.chunk([request.content])
        embedder = get_embedder()

        try:
            embedded_chunks = await run_in_threadpool(embedder.embed_many, chunks)
        except Exception as exc:
            logger.error("embedding_ingest_failed", error_type=type(exc).__name__, error_msg=str(exc))
            raise HTTPException(status_code=500, detail="Error al generar los embeddings.") from exc

        document_id = await _store.persist_document_with_chunks(
            session,
            source_path=request.source_path,
            document_type=request.document_type,
            doc_metadata={
                "budget_id": request.content.budget_id,
                "client_sector": request.content.client_metadata.sector,
                "year": request.content.year,
            },
            embedded_chunks=embedded_chunks,
        )
        # Commit al salir del bloque `async with session.begin()`.

    ingestion_time_ms = round((time.perf_counter() - started) * 1000)
    total_tokens = sum(chunk.token_count for chunk in chunks)
    stats = IngestStats(
        document_id=document_id,
        chunks_created=len(embedded_chunks),
        total_tokens=total_tokens,
        estimated_cost_usd=embedder.estimate_cost_usd(total_tokens),
    )
    logger.info("embedding_ingest_completed", **stats.model_dump())

    return IngestResponse(
        document_id=document_id,
        chunks_created=len(embedded_chunks),
        embedding_dimension=len(embedded_chunks[0].embedding) if embedded_chunks else 0,
        ingestion_time_ms=ingestion_time_ms,
    )


@router.post("/search", response_model=SearchResponse, tags=["search"])
async def search(request: SearchRequest, session: AsyncSession = Depends(get_session)) -> SearchResponse:
    started = time.perf_counter()
    embedder = get_embedder()

    try:
        query_vector = await run_in_threadpool(embedder.embed_one, request.query)
    except Exception as exc:
        logger.error("search_failed", error_type=type(exc).__name__, error_msg=str(exc))
        raise HTTPException(status_code=500, detail="Error al generar el embedding de la consulta.") from exc

    rows = await _store.search(session, query_vector=query_vector, k=request.k)

    search_time_ms = round((time.perf_counter() - started) * 1000)
    response = SearchResponse(
        query=request.query,
        k=request.k,
        search_time_ms=search_time_ms,
        results=[
            SearchHit(
                chunk_id=row.id,
                document_id=row.document_id,
                chunk_type=row.chunk_type,
                content=row.content,
                distance=float(row.distance),
                metadata=row.metadata_,
            )
            for row in rows
        ],
    )
    logger.info(
        "search_completed",
        query=request.query[:80],
        k=request.k,
        results=len(response.results),
        search_time_ms=search_time_ms,
    )
    return response
