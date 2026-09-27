import hashlib
import json
import time
from dataclasses import dataclass

from app.config import get_settings


@dataclass
class _Entry:
    value: dict
    expires_at: float


class ExactMatchCache:
    """
    In-memory exact-match cache keyed by SHA-256(system + user + model).

    The system prompt already embeds the prompt version and CAG examples, so
    changing either invalidates the cache automatically (different hash).
    """

    def __init__(self, ttl: int | None = None) -> None:
        self._ttl = ttl if ttl is not None else get_settings().CACHE_TTL
        self._store: dict[str, _Entry] = {}

    def _key(self, system: str, user: str, model: str) -> str:
        raw = json.dumps({"system": system, "user": user, "model": model}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, system: str, user: str, model: str) -> dict | None:
        key = self._key(system, user, model)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, system: str, user: str, model: str, value: dict) -> None:
        key = self._key(system, user, model)
        self._store[key] = _Entry(value=value, expires_at=time.time() + self._ttl)

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


cache = ExactMatchCache()
