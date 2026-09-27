"""Esquemas del pipeline de retrieval: query estructurada y resultado de busqueda."""

from typing import Literal

from pydantic import BaseModel, Field


class EstimationQuery(BaseModel):
    """Query estructurada extraida de una transcripcion de reunion."""

    function: str = Field(description="Funcion principal del producto, en 3-7 palabras.")
    technologies: list[str] = Field(
        default_factory=list,
        description="Tecnologias, servicios o integraciones especificas mencionadas.",
    )
    sector: str | None = Field(
        default=None,
        description="Sector o vertical si se menciona explicitamente.",
    )
    scale: Literal["pilot", "small", "medium", "large"] | None = Field(
        default=None,
        description="Escala del proyecto, si es inferible de la conversacion.",
    )
    country: str | None = Field(default=None, description="Ambito geografico si se menciona.")
    regulations: list[str] = Field(
        default_factory=list,
        description="Marcos regulatorios mencionados (GDPR, HIPAA, etc.).",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Requisitos no negociables o restricciones explicitas.",
    )


class RetrievedChunk(BaseModel):
    """Un chunk devuelto por el retriever, con su distancia a la query.

    `distance` es `None` para chunks que solo vinieron de la rama lexica de una
    busqueda hibrida (no tienen una distancia coseno propia). `budget_id`
    identifica el presupuesto historico de origen (Sesion 07 ya lo persiste en
    `chunk.metadata_`); se usa para medir precision@k a nivel de presupuesto en
    `scripts/measure_retrieval.py`, no solo a nivel de chunk.
    """

    id: int
    content: str
    sector: str | None
    project_year: int | None
    chunk_type: str
    distance: float | None
    budget_id: str | None = None


class RetrievalResult(BaseModel):
    """Resultado de una busqueda: chunks + senal de confianza."""

    chunks: list[RetrievedChunk]
    low_confidence: bool
    candidates_evaluated: int
