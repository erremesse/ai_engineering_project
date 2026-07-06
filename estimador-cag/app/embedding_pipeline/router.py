import structlog
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.embedder import get_embedder
from app.embedding_pipeline.schemas import IngestRequest, IngestResponse, IngestStats

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

logger = structlog.get_logger()

_chunker = JSONStructuralChunker()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest) -> IngestResponse:
    chunks = _chunker.chunk(request.budgets)
    embedder = get_embedder()

    try:
        embedded_chunks = await run_in_threadpool(embedder.embed_many, chunks)
    except Exception as exc:
        logger.error("embedding_ingest_failed", error_type=type(exc).__name__, error_msg=str(exc))
        raise HTTPException(status_code=500, detail="Error al generar los embeddings.") from exc

    total_tokens = sum(chunk.token_count for chunk in chunks)
    stats = IngestStats(
        total_budgets=len(request.budgets),
        total_chunks=len(chunks),
        total_tokens=total_tokens,
        estimated_cost_usd=embedder.estimate_cost_usd(total_tokens),
    )
    logger.info(
        "embedding_ingest_completed",
        total_budgets=stats.total_budgets,
        total_chunks=stats.total_chunks,
        total_tokens=stats.total_tokens,
        estimated_cost_usd=stats.estimated_cost_usd,
    )
    return IngestResponse(chunks=embedded_chunks, stats=stats)
