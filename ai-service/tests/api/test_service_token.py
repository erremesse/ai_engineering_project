"""X-Service-Token middleware (Sesion 15): el servicio IA solo acepta llamadas
de servicios que conocen AI_SERVICE_TOKEN; /health queda libre para Docker.

Usa GET /api/v1/cag/preview como ruta protegida: no toca LLM ni base de datos.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

TOKEN = "test-service-token"
PROTECTED = "/api/v1/cag/preview"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "AI_SERVICE_TOKEN", TOKEN)
    return TestClient(app)


def test_health_is_exempt(client):
    assert client.get("/health").status_code == 200


def test_missing_token_is_rejected(client):
    response = client.get(PROTECTED)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "X-Service-Token"


def test_wrong_token_is_rejected(client):
    assert client.get(PROTECTED, headers={"X-Service-Token": "nope"}).status_code == 401


def test_valid_token_is_accepted(client):
    response = client.get(PROTECTED, headers={"X-Service-Token": TOKEN})
    assert response.status_code == 200
    body = response.json()
    assert body["system_prompt"]
    assert len(body["examples"]) == body["max_examples"]


def test_guard_disabled_without_token(monkeypatch):
    monkeypatch.setattr(get_settings(), "AI_SERVICE_TOKEN", None)
    assert TestClient(app).get(PROTECTED).status_code == 200
