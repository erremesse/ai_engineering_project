"""
Unit tests for ExactMatchCache.
No LLM calls — pure in-memory logic only.
"""
import time

import pytest

from app.services.cache import ExactMatchCache

_SYSTEM = "You are an estimator."
_USER = "Estimate a web app."
_MODEL = "estimator"
_RESULT = {
    "text": "40 hours",
    "model": "claude-haiku-4-5",
    "provider": "anthropic",
    "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
}


@pytest.fixture
def c() -> ExactMatchCache:
    return ExactMatchCache(ttl=60)


def test_miss_on_empty_cache(c):
    assert c.get(_SYSTEM, _USER, _MODEL) is None


def test_hit_after_set(c):
    c.set(_SYSTEM, _USER, _MODEL, _RESULT)
    assert c.get(_SYSTEM, _USER, _MODEL) == _RESULT


def test_key_is_deterministic(c):
    c.set(_SYSTEM, _USER, _MODEL, _RESULT)
    assert c.get(_SYSTEM, _USER, _MODEL) == _RESULT
    assert c.get(_SYSTEM, _USER, _MODEL) == _RESULT


def test_different_user_prompt_is_different_entry(c):
    c.set(_SYSTEM, _USER, _MODEL, _RESULT)
    assert c.get(_SYSTEM, "different query", _MODEL) is None


def test_different_system_prompt_is_different_entry(c):
    c.set(_SYSTEM, _USER, _MODEL, _RESULT)
    assert c.get("different system", _USER, _MODEL) is None


def test_entry_expires_after_ttl():
    c = ExactMatchCache(ttl=0.05)  # 50 ms
    c.set(_SYSTEM, _USER, _MODEL, _RESULT)
    assert c.get(_SYSTEM, _USER, _MODEL) == _RESULT
    time.sleep(0.1)
    assert c.get(_SYSTEM, _USER, _MODEL) is None


def test_clear_removes_all_entries(c):
    c.set(_SYSTEM, _USER, _MODEL, _RESULT)
    c.clear()
    assert c.size == 0
    assert c.get(_SYSTEM, _USER, _MODEL) is None


def test_size_reflects_stored_entries(c):
    assert c.size == 0
    c.set(_SYSTEM, _USER, _MODEL, _RESULT)
    assert c.size == 1
    c.set(_SYSTEM, "another query", _MODEL, _RESULT)
    assert c.size == 2
