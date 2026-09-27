from pydantic import BaseModel, Field

from app.schemas.estimation import EstimationResponse, TokenUsage
from app.sessions.models import ProjectMetadata


class SessionCreated(BaseModel):
    session_id: str = Field(description="Identificador UUID v4 de la sesion creada.")


class SessionStateResponse(BaseModel):
    session_id: str
    turn_count: int = Field(description="Numero de turnos almacenados en el historial.")
    metadata: ProjectMetadata


class EstimationSessionResponse(EstimationResponse):
    """Respuesta del endpoint conversacional: extiende EstimationResponse con estado de sesion."""

    session_id: str
    turn_count: int = Field(description="Numero de turnos tras este envio.")
    metadata: ProjectMetadata = Field(description="Metadata del proyecto actualizada tras este turno.")
