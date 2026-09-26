"""Orquestador del pipeline RAG: reformulacion -> retrieval -> augmentation -> generacion.

Cinco etapas encadenadas, cada una logueada por separado (`log_stage`) para poder
depurar cual fallo o degrado la calidad de una estimacion concreta.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.generation.context_assembler import (
    build_context_block,
    truncate_to_token_budget,
)
from app.generation.observability import log_stage
from app.generation.prompt_builder import ESTIMATOR_SYSTEM_PROMPT, build_user_prompt
from app.generation.schemas import Estimate
from app.retrieval.query_reformulator import compose_search_text, reformulate
from app.retrieval.retriever import search_chunks
from app.retrieval.schemas import RetrievedChunk
from app.services.llm_service import generate_structured

logger = structlog.get_logger()
settings = get_settings()


def validate_citations(estimate: Estimate, retrieved_chunks: list[RetrievedChunk]) -> list[int]:
    """Ids de source citados por el modelo que NO estaban entre los chunks recuperados."""
    valid_ids = {chunk.id for chunk in retrieved_chunks}
    cited_ids: set[int] = {citation.source_id for citation in estimate.sources}
    for component in estimate.cost_breakdown:
        cited_ids.update(component.sources)
    return sorted(cited_ids - valid_ids)


def _drop_invalid_citations(estimate: Estimate, invalid_ids: list[int]) -> Estimate:
    invalid = set(invalid_ids)
    estimate.sources = [s for s in estimate.sources if s.source_id not in invalid]
    for component in estimate.cost_breakdown:
        component.sources = [sid for sid in component.sources if sid not in invalid]
    return estimate


def _insufficient_estimate(explanation: str) -> Estimate:
    return Estimate(
        total_engineer_days=None,
        cost_breakdown=[],
        duration_weeks=None,
        sources=[],
        assumptions=[],
        confidence="insufficient",
        reasoning="No hay evidencia suficiente en el corpus historico para estimar este proyecto.",
        insufficient_context_explanation=explanation,
    )


async def estimate_from_transcript(
    session: AsyncSession,
    transcript: str,
    idempotency_key: str | None = None,
) -> Estimate:
    if idempotency_key:
        structlog.contextvars.bind_contextvars(idempotency_key=idempotency_key)

    with log_stage("reformulation"):
        structured_query = await reformulate(transcript)

    with log_stage("retrieval", sector=structured_query.sector) as stage_log:
        result = await search_chunks(
            session,
            query_text=compose_search_text(structured_query),
            top_k=settings.RAG_TOP_K,
            distance_threshold=settings.RAG_DISTANCE_THRESHOLD,
            sectors=[structured_query.sector] if structured_query.sector else None,
        )
        stage_log.info(
            "retrieval.chunks",
            count=len(result.chunks),
            low_confidence=result.low_confidence,
        )

    if result.low_confidence:
        return _insufficient_estimate(
            "No se encontraron proyectos historicos suficientemente similares en el "
            "corpus (ningun chunk supero el umbral de distancia configurado). El "
            "equipo comercial deberia revisar esta estimacion manualmente."
        )

    with log_stage("context_assembly", chunks=len(result.chunks)):
        truncated = truncate_to_token_budget(result.chunks, settings.RAG_MAX_CONTEXT_TOKENS)
        context_block = build_context_block(truncated)

    with log_stage("generation"):
        estimate = await generate_structured(
            ESTIMATOR_SYSTEM_PROMPT,
            build_user_prompt(context_block, structured_query),
            Estimate,
        )

    with log_stage("validation") as stage_log:
        invalid_ids = validate_citations(estimate, truncated)
        if invalid_ids:
            stage_log.warning("citation_validation_failed", invalid_source_ids=invalid_ids)
            estimate = _drop_invalid_citations(estimate, invalid_ids)

    return estimate
