from typing import Literal

from pydantic import BaseModel, Field

Sector = Literal["finance", "ecommerce", "healthcare", "industrial"]
Complexity = Literal["low", "medium", "high"]


class ClientMetadata(BaseModel):
    """Metadatos del cliente asociado a un presupuesto historico."""

    name: str = Field(description="Nombre del cliente.")
    sector: Sector = Field(description="Sector de actividad del cliente.")
    country: str = Field(description="Codigo de pais ISO del cliente (ej. ES, MX).")


class BudgetComponent(BaseModel):
    """Un componente individual dentro de un presupuesto historico."""

    component_id: str = Field(description="Identificador del componente dentro del presupuesto.")
    name: str = Field(description="Nombre corto del componente.")
    description: str = Field(description="Descripcion detallada del alcance del componente.")
    tech_stack: list[str] = Field(description="Tecnologias empleadas en el componente.")
    estimated_hours: int = Field(ge=0, description="Horas estimadas para el componente.")
    complexity: Complexity = Field(description="Complejidad estimada del componente.")
    dependencies: list[str] = Field(
        default_factory=list,
        description="component_id de otros componentes de los que depende este.",
    )


class Budget(BaseModel):
    """Un presupuesto historico completo, con sus componentes."""

    budget_id: str = Field(description="Identificador unico del presupuesto.")
    client_metadata: ClientMetadata = Field(description="Metadatos del cliente.")
    project_summary: str = Field(description="Resumen del proyecto presupuestado.")
    main_technology: str = Field(description="Tecnologia principal del proyecto.")
    year: int = Field(description="Ano del presupuesto.")
    total_estimated_hours: int = Field(ge=0, description="Horas totales estimadas del presupuesto.")
    components: list[BudgetComponent] = Field(description="Componentes que forman el presupuesto.")


class Chunk(BaseModel):
    """Un fragmento de texto listo para ser embebido."""

    chunk_id: str = Field(description="Identificador trazable del chunk: {budget_id}::{component_id}.")
    text: str = Field(description="Texto del chunk, listo para pasar al modelo de embeddings.")
    metadata: dict = Field(description="Campos filtrables asociados al chunk (no se embeben).")
    token_count: int = Field(ge=0, description="Numero de tokens del campo text segun el tokenizer del modelo.")


class EmbeddedChunk(Chunk):
    """Un chunk ya vectorizado."""

    embedding: list[float] = Field(description="Vector de embedding generado por el modelo.")


class IngestRequest(BaseModel):
    """Payload de entrada del endpoint de ingesta."""

    budgets: list[Budget] = Field(description="Presupuestos historicos a trocear y vectorizar.")


class IngestStats(BaseModel):
    """Estadisticas agregadas de una ingesta."""

    total_budgets: int = Field(description="Numero de presupuestos procesados.")
    total_chunks: int = Field(description="Numero de chunks generados.")
    total_tokens: int = Field(description="Numero total de tokens embebidos.")
    estimated_cost_usd: float = Field(description="Coste estimado en USD de la llamada al modelo de embeddings.")


class IngestResponse(BaseModel):
    """Payload de salida del endpoint de ingesta."""

    chunks: list[EmbeddedChunk] = Field(description="Chunks vectorizados.")
    stats: IngestStats = Field(description="Estadisticas agregadas de la ingesta.")
