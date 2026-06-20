import uuid
import structlog
from fastapi import FastAPI, Request

from app.logging_config import configure_logging
from app.routers import estimations

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


@app.get("/health")
async def health():
    return {"status": "healthy"}
