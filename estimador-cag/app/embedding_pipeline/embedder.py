import time
from abc import ABC, abstractmethod

import httpx
import structlog
from openai import OpenAI, RateLimitError

from app.config import get_settings
from app.embedding_pipeline.schemas import Chunk, EmbeddedChunk

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = (1, 2, 4)

# Precio de text-embedding-3-small a fecha de este ejercicio (2026-07).
# Verificar en https://openai.com/api/pricing si ha cambiado.
OPENAI_PRICE_PER_MILLION_TOKENS_USD = 0.02

logger = structlog.get_logger()


class Embedder(ABC):
    """Interfaz comun a los distintos backends de embeddings soportados."""

    #: Coste por millon de tokens de entrada. 0.0 para backends locales.
    price_per_million_tokens_usd: float = 0.0

    def embed_one(self, text: str) -> list[float]:
        return self._embed_batch([text])[0]

    def embed_many(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        embedded_chunks: list[EmbeddedChunk] = []
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            texts = [chunk.text for chunk in batch]
            total_tokens = sum(chunk.token_count for chunk in batch)

            t0 = time.perf_counter()
            vectors = self._embed_batch(texts)
            latency_ms = round((time.perf_counter() - t0) * 1000)

            logger.info(
                "embedding_batch_completed",
                provider=self.__class__.__name__,
                batch_size=len(batch),
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )

            for chunk, embedding in zip(batch, vectors):
                embedded_chunks.append(EmbeddedChunk(**chunk.model_dump(), embedding=embedding))

        return embedded_chunks

    def estimate_cost_usd(self, total_tokens: int) -> float:
        return round(total_tokens / 1_000_000 * self.price_per_million_tokens_usd, 6)

    @abstractmethod
    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Llama al backend de embeddings y devuelve un vector por texto, en el mismo orden."""


class OpenAIEmbedder(Embedder):
    """Genera embeddings con text-embedding-3-small via la API de OpenAI."""

    price_per_million_tokens_usd = OPENAI_PRICE_PER_MILLION_TOKENS_USD

    def __init__(self) -> None:
        settings = get_settings()
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=texts)
                return [item.embedding for item in response.data]
            except RateLimitError:
                if attempt == MAX_RETRIES:
                    raise
                wait_seconds = RETRY_BACKOFF_SECONDS[attempt]
                logger.warning("embedding_rate_limited", attempt=attempt + 1, wait_seconds=wait_seconds)
                time.sleep(wait_seconds)


class OllamaEmbedder(Embedder):
    """Genera embeddings con un modelo local servido por Ollama (coste 0)."""

    price_per_million_tokens_usd = 0.0

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.OLLAMA_API_BASE:
            raise ValueError("OLLAMA_API_BASE debe estar configurado para usar EMBEDDING_PROVIDER=ollama")
        self._base_url = settings.OLLAMA_API_BASE.rstrip("/")
        self._model = settings.OLLAMA_EMBEDDING_MODEL

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = httpx.post(
                    f"{self._base_url}/api/embed",
                    json={"model": self._model, "input": texts},
                    timeout=60.0,
                )
                response.raise_for_status()
                return response.json()["embeddings"]
            except httpx.HTTPError:
                if attempt == MAX_RETRIES:
                    raise
                wait_seconds = RETRY_BACKOFF_SECONDS[attempt]
                logger.warning("embedding_request_failed", attempt=attempt + 1, wait_seconds=wait_seconds)
                time.sleep(wait_seconds)


def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER == "ollama":
        return OllamaEmbedder()
    return OpenAIEmbedder()
