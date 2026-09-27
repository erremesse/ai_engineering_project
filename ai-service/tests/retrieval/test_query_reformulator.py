"""
Unit tests for query_reformulator.
No LLM calls — generate_structured/generate_from_messages are monkeypatched.
"""
import pytest

from app.retrieval import query_reformulator
from app.retrieval.schemas import EstimationQuery

_QUERY = EstimationQuery(
    function="patient appointment scheduling",
    technologies=["python_django"],
    sector="healthcare",
    scale="medium",
    country=None,
    regulations=["GDPR"],
    constraints=[],
)


def test_compose_search_text_full_query():
    text = query_reformulator.compose_search_text(_QUERY)
    assert text == (
        "patient appointment scheduling. with python_django. "
        "for the healthcare sector. compliant with GDPR."
    )


def test_compose_search_text_minimal_query():
    minimal = EstimationQuery(function="mobile app for reservations")
    assert query_reformulator.compose_search_text(minimal) == "mobile app for reservations."


@pytest.mark.asyncio
async def test_reformulate_returns_structured_query_on_success(monkeypatch):
    async def fake_generate_structured(system, user, schema):
        return _QUERY

    monkeypatch.setattr(query_reformulator, "generate_structured", fake_generate_structured)

    result = await query_reformulator.reformulate("some transcript")

    assert result == _QUERY


@pytest.mark.asyncio
async def test_reformulate_falls_back_to_rewrite_when_structured_extraction_fails(monkeypatch):
    async def failing_generate_structured(system, user, schema):
        raise ValueError("provider does not support strict json_schema")

    async def fake_generate_from_messages(messages):
        return {"text": "telemedicine platform with video consultations"}

    monkeypatch.setattr(query_reformulator, "generate_structured", failing_generate_structured)
    monkeypatch.setattr(query_reformulator, "generate_from_messages", fake_generate_from_messages)

    result = await query_reformulator.reformulate("a messy transcript")

    assert isinstance(result, EstimationQuery)
    assert result.function == "telemedicine platform with video consultations"
    assert result.technologies == []
    assert result.sector is None
