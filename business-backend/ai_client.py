"""Cliente HTTP del servicio IA (Sesion 15).

Unico punto por el que el business-backend habla con el servicio IA. Toda
peticion lleva X-Service-Token (AI_SERVICE_TOKEN); las rutas RAG llevan ademas
X-API-Key (ESTIMATE_API_KEY), la capa de la Sesion 09.

AI_SERVICE_URL usa el nombre de servicio de compose (http://ai-service:8000),
no localhost: dentro de la red de compose cada contenedor tiene su propio
localhost.
"""

import json
import os
from collections.abc import Iterator

import httpx

_TIMEOUT = httpx.Timeout(connect=10, read=300, write=10, pool=5)


class AiServiceClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("AI_SERVICE_URL", "http://localhost:8000").rstrip("/")
        token = os.getenv("AI_SERVICE_TOKEN", "")
        self._rag_api_key = os.getenv("ESTIMATE_API_KEY", "")
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={"X-Service-Token": token} if token else {},
            timeout=_TIMEOUT,
        )

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def cag_preview(self, project_type: str, detail_level: str, output_format: str, n_examples: int) -> dict:
        r = self._http.get(
            "/api/v1/cag/preview",
            params={
                "project_type": project_type,
                "detail_level": detail_level,
                "output_format": output_format,
                "n_examples": n_examples,
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def create_session(self) -> str:
        r = self._http.post("/api/v1/sessions", timeout=10)
        r.raise_for_status()
        return r.json()["session_id"]

    def session_estimate(self, session_id: str, form_data: dict, files: list | None = None) -> dict:
        kwargs: dict = {"data": form_data}
        if files:
            kwargs["files"] = files
        r = self._http.post(f"/api/v1/sessions/{session_id}/estimate", **kwargs)
        r.raise_for_status()
        return r.json()

    def estimate(self, payload: dict) -> dict:
        r = self._http.post("/api/v1/estimate", json=payload)
        r.raise_for_status()
        return r.json()

    def estimate_stream(self, payload: dict, metadata_sink: dict) -> Iterator[str]:
        """Yields text chunks; the trailing \\x00-prefixed JSON chunk goes to metadata_sink."""
        with self._http.stream("POST", "/api/v1/estimate/stream", json=payload) as r:
            r.raise_for_status()
            for chunk in r.iter_text():
                if chunk.startswith("\x00"):
                    metadata_sink.update(json.loads(chunk[1:]))
                else:
                    yield chunk

    def rag_estimate(self, transcript: str) -> dict:
        r = self._http.post(
            "/v1/estimate/from-transcript",
            json={"transcript": transcript},
            headers={"X-API-Key": self._rag_api_key} if self._rag_api_key else {},
        )
        r.raise_for_status()
        return r.json()
