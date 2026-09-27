"""Reciprocal Rank Fusion: merge multiple ranked lists by consensus, not by score.

Cosine distance and ts_rank live on incomparable scales (bounded vs. unbounded,
different distributions per query), so summing raw scores from the vector and
lexical branches would be summing meters with kilograms. RRF sidesteps that by
using only rank positions — a chunk both branches rank reasonably high beats a
chunk only one branch loves, which is exactly the "consensus" behavior hybrid
search is meant to produce.
"""

from collections import defaultdict


def reciprocal_rank_fusion(rankings: list[list[int]], k: int) -> list[int]:
    """Fuse ranked lists of chunk ids into one ranking via RRF.

    Each id's score is the sum, across every ranking it appears in, of
    1 / (k + rank) (rank starting at 1). `k` is the smoothing constant — small
    k lets the very top of each ranking dominate, large k flattens the
    differences; 60 (the value from the original RRF paper) is a robust
    default across domains and rarely the lever worth pulling first.
    """
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] += 1.0 / (k + rank)
    return [chunk_id for chunk_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]
