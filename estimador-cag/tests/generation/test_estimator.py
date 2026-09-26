"""
Unit tests for estimator.validate_citations.
No LLM/DB calls — pure comparison between cited ids and retrieved chunk ids.
"""
from app.generation.estimator import validate_citations
from app.generation.schemas import CostComponent, Estimate, SourceCitation
from app.retrieval.schemas import RetrievedChunk


def _chunk(id_: int) -> RetrievedChunk:
    return RetrievedChunk(
        id=id_, content="c", sector="healthcare", project_year=2024, chunk_type="budget_component", distance=0.1
    )


def _estimate(source_ids: list[int], cost_breakdown_ids: list[int]) -> Estimate:
    return Estimate(
        total_engineer_days=100,
        cost_breakdown=[CostComponent(name="backend", engineer_days=100, sources=cost_breakdown_ids)],
        duration_weeks=4,
        sources=[SourceCitation(source_id=sid, relevance="primary", used_for="backend") for sid in source_ids],
        assumptions=[],
        confidence="high",
        reasoning="reasoning",
    )


def test_validate_citations_returns_empty_when_all_ids_are_valid():
    chunks = [_chunk(1), _chunk(2)]
    estimate = _estimate(source_ids=[1, 2], cost_breakdown_ids=[1])

    assert validate_citations(estimate, chunks) == []


def test_validate_citations_flags_invalid_source_id():
    chunks = [_chunk(1)]
    estimate = _estimate(source_ids=[1, 99], cost_breakdown_ids=[1])

    assert validate_citations(estimate, chunks) == [99]


def test_validate_citations_flags_invalid_id_only_in_cost_breakdown():
    chunks = [_chunk(1)]
    estimate = _estimate(source_ids=[1], cost_breakdown_ids=[1, 42])

    assert validate_citations(estimate, chunks) == [42]


def test_validate_citations_deduplicates_and_sorts_invalid_ids():
    chunks: list[RetrievedChunk] = []
    estimate = _estimate(source_ids=[5, 3], cost_breakdown_ids=[3, 5])

    assert validate_citations(estimate, chunks) == [3, 5]
