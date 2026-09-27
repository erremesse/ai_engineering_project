"""Vista previa del contexto CAG (Sesion 15).

El frontend (business-backend) ya no importa `app.*`: los ejemplos CAG y el
system prompt que mostraba en la barra lateral los pide aqui. No llama al LLM.
"""

from fastapi import APIRouter, Query

from app.context.examples import ESTIMATION_EXAMPLES
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import DetailLevel, EstimationRequest, OutputFormat, ProjectType

router = APIRouter(prefix="/api/v1", tags=["cag"])

_PREVIEW_DESCRIPTION = "Esta es una descripcion de prueba para la vista previa del prompt."


@router.get("/cag/preview")
async def cag_preview(
    project_type: ProjectType = Query(ProjectType.WEB_SAAS),
    detail_level: DetailLevel = Query(DetailLevel.MEDIUM),
    output_format: OutputFormat = Query(OutputFormat.PHASES_TABLE),
    n_examples: int = Query(len(ESTIMATION_EXAMPLES), ge=1),
) -> dict:
    request = EstimationRequest(
        description=_PREVIEW_DESCRIPTION,
        project_type=project_type,
        detail_level=detail_level,
        output_format=output_format,
        n_examples=n_examples,
    )
    system_prompt, _ = render_estimation_prompt(request)
    return {
        "system_prompt": system_prompt,
        "examples": ESTIMATION_EXAMPLES[:n_examples],
        "max_examples": len(ESTIMATION_EXAMPLES),
    }
