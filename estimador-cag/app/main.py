import uuid
import structlog
from fastapi import FastAPI, Request

from app.api.routers import estimate, retrieval
from app.embedding_pipeline import router as embedding_router
from app.logging_config import configure_logging
from app.routers import estimations, sessions

configure_logging()

logger = structlog.get_logger()

app = FastAPI(
    title="Estimador CAG",
    description="Sistema de estimación de software con arquitectura CAG",
    version="0.1.0",
)


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
app.include_router(embedding_router.router)
app.include_router(retrieval.router, prefix="/v1/retrieval", tags=["retrieval"])
app.include_router(estimate.router, prefix="/v1/estimate", tags=["estimate"])


@app.get("/health")
async def health():
    return {"status": "healthy"}
