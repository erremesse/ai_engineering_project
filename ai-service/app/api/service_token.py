"""Autenticacion entre servicios (Sesion 15): business-backend -> servicio IA.

Estar en la red interna de compose no basta para llamar al servicio IA: toda
peticion debe traer la cabecera X-Service-Token con el secreto compartido
AI_SERVICE_TOKEN. Es un middleware (y no una dependencia por router) para que
ninguna ruta nueva quede desprotegida por olvido; /health y la documentacion
quedan exentos para que el healthcheck de Docker funcione sin secreto.

Capa independiente de la X-API-Key de security.py (Sesion 09), que sigue
protegiendo las rutas RAG por encima de esta.
"""

import secrets

import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from app.config import get_settings

logger = structlog.get_logger()

SERVICE_TOKEN_HEADER = "X-Service-Token"
EXEMPT_PATHS = frozenset({"/health", "/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"})


async def service_token_middleware(request: Request, call_next) -> Response:
    expected = get_settings().AI_SERVICE_TOKEN
    if not expected:
        return await call_next(request)
    if request.method == "OPTIONS" or request.url.path in EXEMPT_PATHS:
        return await call_next(request)

    provided = request.headers.get(SERVICE_TOKEN_HEADER)
    if not provided or not secrets.compare_digest(provided, expected):
        logger.warning(
            "service_token_rejected",
            path=request.url.path,
            reason="missing" if not provided else "mismatch",
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or missing service token"},
            headers={"WWW-Authenticate": SERVICE_TOKEN_HEADER},
        )
    return await call_next(request)
