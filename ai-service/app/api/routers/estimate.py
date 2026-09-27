"""Endpoint que orquesta el pipeline RAG completo: transcripcion -> estimacion."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security import require_estimate_key
from app.db.session import get_session
from app.generation.estimator import estimate_from_transcript
from app.generation.schemas import Estimate

router = APIRouter()
logger = structlog.get_logger()


class EstimateRequest(BaseModel):
    transcript: str = Field(min_length=100, max_length=50000)
    idempotency_key: str | None = Field(default=None, max_length=128)


@router.post("/from-transcript", response_model=Estimate)
async def estimate(
    req: EstimateRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_estimate_key),
) -> Estimate:
    try:
        return await estimate_from_transcript(
            session,
            transcript=req.transcript,
            idempotency_key=req.idempotency_key,
        )
    except Exception as exc:
        logger.error("estimate_from_transcript_failed", error_type=type(exc).__name__, error_msg=str(exc))
        raise HTTPException(
            status_code=502,
            detail="No se pudo generar una estimacion estructurada a partir de la transcripcion.",
        ) from exc
