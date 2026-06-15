from enum import Enum
from pydantic import BaseModel, Field


class ProjectType(str, Enum):
    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


class EstimationRequest(BaseModel):
    """Datos de entrada para generar una estimacion de proyecto de software."""

    description: str = Field(
        min_length=20,
        max_length=2000,
        description="Descripcion del proyecto de software a estimar.",
    )
    project_type: ProjectType = Field(
        description="Tipo de proyecto (app movil, web/SaaS, herramienta interna, pipeline de datos)."
    )
    detail_level: DetailLevel = Field(
        description="Nivel de detalle de la estimacion: resumen, medio o detallado."
    )
    output_format: OutputFormat = Field(
        description="Formato de salida: tabla de fases, partidas de presupuesto o narrativo."
    )
    n_examples: int | None = Field(
        default=None,
        ge=1,
        description="Numero de ejemplos CAG a inyectar en el prompt. Por defecto usa NUM_CAG_EXAMPLES.",
    )


class TokenUsage(BaseModel):
    """Consumo de tokens de la llamada al LLM."""

    input_tokens: int = Field(description="Tokens de entrada (prompt).")
    output_tokens: int = Field(description="Tokens de salida (completion).")
    total_tokens: int = Field(description="Total de tokens consumidos.")


class EstimationResponse(BaseModel):
    """Respuesta generada por el servicio de estimacion."""

    text: str = Field(description="Texto de la estimacion generada por el LLM.")
    prompt_version: str = Field(description="Version del prompt utilizado para generar la estimacion.")
    model: str = Field(description="Identificador del modelo LLM que respondio.")
    provider: str = Field(description="Proveedor del LLM (anthropic, openai, ollama...).")
    usage: TokenUsage = Field(description="Metricas de tokens consumidos en la llamada.")
