"""
Unit tests for reciprocal_rank_fusion.
Pure function — no DB/LLM calls.
"""
from app.retrieval.fusion import reciprocal_rank_fusion


def test_consensus_beats_a_single_top_rank():
    # id 2 is 2nd in ranking A and 1st in ranking B (consensus);
    # id 1 is 1st in A but absent from B.
    rankings = [[1, 2, 3], [2, 3]]

    fused = reciprocal_rank_fusion(rankings, k=60)

    assert fused[0] == 2


def test_id_present_in_every_ranking_ranks_first():
    rankings = [[5, 1, 2], [1, 5, 3], [1, 2, 5]]

    fused = reciprocal_rank_fusion(rankings, k=60)

    assert fused[0] == 1


def test_single_ranking_is_returned_unchanged_in_order():
    rankings = [[10, 20, 30]]

    assert reciprocal_rank_fusion(rankings, k=60) == [10, 20, 30]


def test_empty_rankings_returns_empty_list():
    assert reciprocal_rank_fusion([], k=60) == []
    assert reciprocal_rank_fusion([[], []], k=60) == []


def test_smaller_k_amplifies_top_rank_dominance():
    # id 1 is always rank 1; id 2 is always rank 2. With a very small k the gap
    # between them should be larger (relatively) than with a very large k.
    rankings = [[1, 2], [1, 2]]

    scores_small_k = {cid: 1.0 / (1 + rank) for rank, cid in enumerate([1, 2], start=1)}
    scores_large_k = {cid: 1.0 / (1000 + rank) for rank, cid in enumerate([1, 2], start=1)}

    gap_small_k = scores_small_k[1] - scores_small_k[2]
    gap_large_k = scores_large_k[1] - scores_large_k[2]

    assert gap_small_k > gap_large_k
    assert reciprocal_rank_fusion(rankings, k=1) == [1, 2]
    assert reciprocal_rank_fusion(rankings, k=1000) == [1, 2]
