import uuid
import structlog
from fastapi import FastAPI, Request

from app.api.routers import estimate, retrieval
from app.api.service_token import service_token_middleware
from app.embedding_pipeline import router as embedding_router
from app.logging_config import configure_logging
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
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=str(uuid.uuid4())[:8],
        endpoint=request.url.path,
        method=request.method,
    )
    return await call_next(request)


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
