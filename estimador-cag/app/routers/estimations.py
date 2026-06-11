from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.estimation import EstimationRequest, EstimationResponse
from app.services.llm_service import generate_estimation, stream_estimation

router = APIRouter(prefix="/api/v1", tags=["estimations"])


@router.post("/estimate", response_model=EstimationResponse)
async def estimate(request: EstimationRequest):
    result = await generate_estimation(request.transcription)
    return result


@router.post("/estimate/stream")
async def estimate_stream(request: EstimationRequest):
    return StreamingResponse(
        stream_estimation(request.transcription),
        media_type="text/plain",
    )