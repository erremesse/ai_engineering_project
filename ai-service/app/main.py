import time
import uuid
import structlog
from fastapi import FastAPI, Request

from app.api.routers import estimate, retrieval
from app.api.service_token import service_token_middleware
from app.embedding_pipeline import router as embedding_router
from app.logging_config import configure_logging
from app.observability import (
    estimation_endpoint,
    metered_body,
    record_request_metrics,
    start_usage_tracking,
)
from app.routers import cag, estimations, sessions

configure_logging()

logger = structlog.get_logger()

app = FastAPI(
    title="Estimador CAG",
    description="Sistema de estimación de software con arquitectura CAG",
    version="0.1.0",
)

# Registered before request_context_middleware so it runs *inside* it (Starlette
# runs the last-registered middleware first): rejected calls still get a request_id.
app.middleware("http")(service_token_middleware)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        endpoint=request.url.path,
        method=request.method,
    )
    endpoint = estimation_endpoint(request.method, request.url.path)
    if endpoint is None:
        return await call_next(request)

    # Estimation endpoints emit production metrics (Sesion 16). Being the outermost
    # middleware, the service-token 401s are measured too.
    usage = start_usage_tracking()
    started = time.perf_counter()

    def finish(status_code: int) -> None:
        record_request_metrics(
            request_id=request_id,
            endpoint=endpoint,
            status_code=status_code,
            latency_ms=(time.perf_counter() - started) * 1000,
            usage=usage,
        )

    try:
        response = await call_next(request)
    except Exception:
        finish(500)
        raise
    # Recorded once the body is fully sent: for /api/v1/estimate/stream the LLM is
    # still generating (and adding tokens) when call_next returns.
    response.body_iterator = metered_body(response.body_iterator, lambda: finish(response.status_code))
    return response


app.include_router(estimations.router)
app.include_router(sessions.router)
app.include_router(cag.router)
app.include_router(embedding_router.router)
app.include_router(retrieval.router, prefix="/v1/retrieval", tags=["retrieval"])
app.include_router(estimate.router, prefix="/v1/estimate", tags=["estimate"])


@app.get("/health")
async def health():
    # Liveness only: cheap, no LLM and no DB call. Exempt from X-Service-Token
    # so the Docker healthcheck works without the secret.
    return {"status": "healthy"}
