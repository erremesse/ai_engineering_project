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

    # CAG context
    NUM_CAG_EXAMPLES: int = 5

    # Cache
    CACHE_TTL: int = 86_400  # seconds — 24 h default

    # Pydantic v2 usa model_config para definir el archivo .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Instanciamos la configuración una sola vez y la reutilizamos en toda la aplicación
@lru_cache
def get_settings() -> Settings:
    return Settings()
