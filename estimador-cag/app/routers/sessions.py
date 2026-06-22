from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.prompts.loader import render_session_prompt
from app.schemas.estimation import DetailLevel, EstimationRequest, OutputFormat, ProjectType, TokenUsage
from app.schemas.sessions import EstimationSessionResponse, SessionCreated, SessionStateResponse
from app.services.attachment_service import attachment_service
from app.services.llm_service import generate_from_messages
from app.sessions import metadata_extractor, session_store

_PROMPT_VERSION = "v1"

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.post("/sessions", response_model=SessionCreated, status_code=201)
async def create_new_session() -> SessionCreated:
    """Crea una sesion conversacional vacia y devuelve su identificador."""
    session = session_store.create()
    return SessionCreated(session_id=session.session_id)


@router.get("/sessions/{session_id}", response_model=SessionStateResponse)
async def get_session_state(session_id: str) -> SessionStateResponse:
    """Devuelve el estado actual de la sesion (util para debugging en el cliente)."""
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")
    return SessionStateResponse(
        session_id=session_id,
        turn_count=session.history.turn_count(),
        metadata=session.metadata,
    )


@router.post("/sessions/{session_id}/estimate", response_model=EstimationSessionResponse)
async def estimate_session(
    session_id: str,
    transcript: str = Form(..., min_length=20, max_length=2000),
    project_type: ProjectType = Form(...),
    detail_level: DetailLevel = Form(...),
    output_format: OutputFormat = Form(...),
    n_examples: int | None = Form(default=None),
    attachments: list[UploadFile] = File(default=[]),
) -> EstimationSessionResponse:
    """Endpoint conversacional: acepta transcripcion y adjuntos opcionales, mantiene historial."""
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")

    # Construir request para el loader (description = transcript original)
    request = EstimationRequest(
        description=transcript,
        project_type=project_type,
        detail_level=detail_level,
        output_format=output_format,
        n_examples=n_examples,
    )

    # Renderizar prompts con metadata actual de la sesion
    system, user_content = render_session_prompt(request, session.metadata)

    # Adjuntar texto extraido de los ficheros al mensaje del usuario
    for file in attachments:
        try:
            extracted = attachment_service.extract_text(file)
            user_content += attachment_service.build_attachment_block(extracted)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    # Construir array de mensajes: system + historial previo + turno actual
    messages = session.history.to_messages(system)
    messages.append({"role": "user", "content": user_content})

    # Llamar al LLM con el historial completo
    result = await generate_from_messages(messages)

    # Actualizar estado de la sesion
    session.history.add_turn(user_content, result["text"])
    session.metadata = metadata_extractor.update(session.metadata, transcript, result["text"])

    return EstimationSessionResponse(
        text=result["text"],
        prompt_version=_PROMPT_VERSION,
        model=result["model"],
        provider=result["provider"],
        usage=TokenUsage(**result["usage"]),
        session_id=session_id,
        turn_count=session.history.turn_count(),
        metadata=session.metadata,
    )
