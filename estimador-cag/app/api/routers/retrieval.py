"""Endpoint de retrieval de bajo nivel: busqueda directa contra pgvector con
filtros, sin pasar por la reformulacion de transcripciones. Util para depurar el
retriever de forma aislada del resto del pipeline."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security import require_retrieval_key
from app.db.session import get_session
from app.retrieval.retriever import search_chunks

router = APIRouter()


class SearchRequest(BaseModel):
    query_text: str = Field(min_length=10, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=30)
    distance_threshold: float = Field(default=0.6, ge=0.0, le=2.0)
    sectors: list[str] | None = None
    project_year_min: int | None = Field(default=None, ge=2010, le=2100)
    project_year_max: int | None = Field(default=None, ge=2010, le=2100)
    chunk_types: list[str] | None = None
    tech_stack: list[str] | None = None


class SearchResponseChunk(BaseModel):
    id: int
    content: str
    sector: str | None
    project_year: int | None
    chunk_type: str
    distance: float


class SearchResponse(BaseModel):
    chunks: list[SearchResponseChunk]
    low_confidence: bool
    total_candidates_considered: int


@router.post("/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_retrieval_key),
) -> SearchResponse:
    result = await search_chunks(
        session,
        query_text=req.query_text,
        top_k=req.top_k,
        distance_threshold=req.distance_threshold,
        sectors=req.sectors,
        project_year_min=req.project_year_min,
        project_year_max=req.project_year_max,
        chunk_types=req.chunk_types,
        tech_stack=req.tech_stack,
    )
    return SearchResponse(
        chunks=[SearchResponseChunk(**chunk.model_dump()) for chunk in result.chunks],
        low_confidence=result.low_confidence,
        total_candidates_considered=result.candidates_evaluated,
    )
