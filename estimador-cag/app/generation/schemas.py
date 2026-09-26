"""Esquema de salida de la estimacion generada a partir de contexto recuperado."""

from typing import Literal

from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    source_id: int
    relevance: Literal["primary", "supporting", "tangential"]
    used_for: str = Field(description="Que componente de la estimacion informo esta fuente.")


class Assumption(BaseModel):
    description: str
    impact: Literal["high", "medium", "low"]
    rationale: str


class CostComponent(BaseModel):
    name: str
    engineer_days: int
    sources: list[int] = Field(description="Ids de source que soportan este componente.")


class Estimate(BaseModel):
    total_engineer_days: int | None
    cost_breakdown: list[CostComponent]
    duration_weeks: int | None
    sources: list[SourceCitation]
    assumptions: list[Assumption]
    confidence: Literal["high", "medium", "low", "insufficient"]
    reasoning: str
    insufficient_context_explanation: str | None = Field(
        default=None,
        description="Si confidence es 'insufficient', explica que informacion falta.",
    )
