from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import EstimationRequest, EstimationResponse, TokenUsage
from app.services.llm_service import generate_estimation, stream_estimation

router = APIRouter(prefix="/api/v1", tags=["estimations"])

_PROMPT_VERSION = "v1"


@router.post("/estimate", response_model=EstimationResponse)
async def estimate(request: EstimationRequest):
    system, user = render_estimation_prompt(request)
    result = await generate_estimation(system, user)
    return EstimationResponse(
        text=result["text"],
        prompt_version=_PROMPT_VERSION,
        model=result["model"],
        provider=result["provider"],
        usage=TokenUsage(**result["usage"]),
    )


@router.post("/estimate/stream")
async def estimate_stream(request: EstimationRequest):
    system, user = render_estimation_prompt(request)
    return StreamingResponse(
        stream_estimation(system, user),
        media_type="text/plain",
    )
