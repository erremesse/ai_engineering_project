from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    LLM_PROVIDER: Literal["openai", "anthropic", "ollama"] = "anthropic"
    ANTHROPIC_MODEL: str = "claude-haiku-4-5"
    OPENAI_MODEL: str = "gpt-4o-mini"
    APP_ENV: str = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"

    # Ollama — optional remote server
    OLLAMA_API_BASE: str | None = None
    OLLAMA_MODELS: str = "llama3.3:70b,deepseek-r1:70b"

    # Embeddings (embedding_pipeline)
    EMBEDDING_PROVIDER: Literal["openai", "ollama"] = "openai"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    # Dimension of the configured embedding model. text-embedding-3-small -> 1536,
    # nomic-embed-text -> 768. Must match EMBEDDING_PROVIDER/OLLAMA_EMBEDDING_MODEL —
    # changing it after data has been ingested requires a new migration and re-embedding
    # the whole corpus (see README, "por que no vector(1536) hardcodeado").
    EMBEDDING_DIMENSION: int = 1536

    # Database (pgvector persistence)
    DATABASE_URL: str = "postgresql+asyncpg://estimator:estimator@localhost:5432/estimator"

    # CAG context
    NUM_CAG_EXAMPLES: int = 5

    # Cache
    CACHE_TTL: int = 86_400  # seconds — 24 h default

    # RAG (retrieval + generation, Sesion 09)
    RETRIEVAL_API_KEY: str | None = None
    ESTIMATE_API_KEY: str | None = None
    RAG_TOP_K: int = 10
    RAG_DISTANCE_THRESHOLD: float = 0.6
    RAG_MAX_CONTEXT_TOKENS: int = 4000

    # Hybrid search + reranking (Sesion 10)
    RAG_SEARCH_MODE: Literal["vector", "hybrid"] = "vector"
    RAG_RERANK_ENABLED: bool = False
    RAG_RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RAG_RECALL_POOL_SIZE: int = 50
    RAG_RRF_K: int = 60

    # Pydantic v2 usa model_config para definir el archivo .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Instanciamos la configuración una sola vez y la reutilizamos en toda la aplicación
@lru_cache
def get_settings() -> Settings:
    return Settings()
