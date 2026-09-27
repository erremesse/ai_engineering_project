"""
Unit tests for context_assembler.
No LLM/DB calls — pure text assembly and truncation logic.
"""
from app.generation.context_assembler import (
    build_context_block,
    reorder_u_pattern,
    truncate_to_token_budget,
)
from app.retrieval.schemas import RetrievedChunk


def _chunk(id_: int, content: str, distance: float | None = 0.1) -> RetrievedChunk:
    return RetrievedChunk(
        id=id_,
        content=content,
        sector="healthcare",
        project_year=2024,
        chunk_type="budget_component",
        distance=distance,
    )


def test_build_context_block_wraps_each_chunk_in_source_tags():
    chunks = [_chunk(1, "First chunk content"), _chunk(2, "Second chunk content")]

    block = build_context_block(chunks)

    assert '<source id="1" sector="healthcare" project_year="2024" chunk_type="budget_component" distance="0.100">' in block
    assert "First chunk content" in block
    assert "</source>" in block
    assert block.count("<source") == 2


def test_truncate_to_token_budget_drops_whole_chunks_never_splits():
    small_chunk = _chunk(1, "short")
    huge_chunk = _chunk(2, "word " * 5000)  # far exceeds any reasonable budget

    selected = truncate_to_token_budget([small_chunk, huge_chunk], max_context_tokens=200)

    assert selected == [small_chunk]
    # The huge chunk must be dropped whole, not present in any truncated form.
    assert all(chunk.id != 2 for chunk in selected)


def test_build_context_block_renders_missing_distance_as_na():
    # Chunks that only came from the lexical branch of a hybrid search have no
    # cosine distance (see retriever.py::_to_chunk).
    block = build_context_block([_chunk(1, "lexical-only content", distance=None)])

    assert 'distance="n/a"' in block


def test_truncate_to_token_budget_keeps_all_when_budget_is_generous():
    chunks = [_chunk(1, "short one"), _chunk(2, "short two")]

    selected = truncate_to_token_budget(chunks, max_context_tokens=4000)

    assert selected == chunks


def test_reorder_u_pattern_puts_rank_two_at_the_end():
    chunks = [_chunk(1, "a"), _chunk(2, "b"), _chunk(3, "c"), _chunk(4, "d")]

    reordered = reorder_u_pattern(chunks)

    assert [c.id for c in reordered] == [1, 3, 4, 2]
