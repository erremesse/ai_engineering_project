"""Autenticacion por API key para los endpoints de RAG (retrieval/estimate).

Los routers de sesiones previas (estimations, sessions, embeddings) se quedan sin
auth, tal cual estaban. Esto solo protege las dos rutas nuevas.
"""

import secrets

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

logger = structlog.get_logger()

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _check_key(provided: str | None, expected: str | None, key_name: str) -> None:
    # `not expected`, not `is None`: a blank `ESTIMATE_API_KEY=` in .env arrives as ""
    # and must disable the check too, as documented in .env.example.
    if not expected:
        logger.warning("api_key_check_disabled", key_name=key_name)
        return
    if provided is None or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def require_retrieval_key(api_key: str | None = Depends(_api_key_header)) -> None:
    _check_key(api_key, get_settings().RETRIEVAL_API_KEY, "retrieval")


def require_estimate_key(api_key: str | None = Depends(_api_key_header)) -> None:
    _check_key(api_key, get_settings().ESTIMATE_API_KEY, "estimate")
