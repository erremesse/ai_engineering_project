from pydantic import BaseModel, Field

class EstimationRequest(BaseModel):
    transcription: str = Field(
        ...,
        min_length=50,
        description="Transcripción de la reunión con el cliente"
    )
    n_examples: int | None = Field(
        default=None,
        ge=1,
        description="Número de ejemplos CAG a inyectar en el prompt (por defecto: NUM_CAG_EXAMPLES)"
    )

class TokenUsage(BaseModel):
    """Token consumption details from the LLM call."""

    input_tokens: int
    output_tokens: int
    total_tokens: int

class EstimationResponse(BaseModel):
    estimation: str
    model: str
    provider: str
    usage: TokenUsage
