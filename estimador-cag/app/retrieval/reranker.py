"""Cross-encoder reranker: recall-then-rerank, second stage.

Unlike `embedding_pipeline.embedder.get_embedder()` (a cheap HTTP client,
recreated per call), the cross-encoder is a local model — loading it is
expensive, so this module keeps a process-wide singleton and only loads it the
first time `.rerank()` is actually called. `sentence_transformers` itself is
imported lazily too (inside `_ensure_loaded`, not at module scope), so simply
importing this module — which happens whenever `app.retrieval.retriever` is
imported — never pulls in `torch` unless reranking is actually used.
"""

import threading

import structlog

from app.config import get_settings
from app.retrieval.schemas import RetrievedChunk

logger = structlog.get_logger()


class Reranker:
    """Cross-encoder reranker for retrieved candidates."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _ensure_loaded(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import CrossEncoder

                    self._model = CrossEncoder(self._model_name)
                    logger.info("reranker_loaded", model=self._model_name)
        return self._model

    def rerank(self, query: str, candidates: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        """Score query-candidate pairs jointly and return the top_k best."""
        if not candidates:
            return []

        model = self._ensure_loaded()
        pairs = [(query, candidate.content) for candidate in candidates]
        scores = model.predict(pairs)

        ranked = sorted(zip(candidates, scores), key=lambda item: item[1], reverse=True)

        logger.info(
            "rerank_completed",
            candidates_in=len(candidates),
            candidates_out=min(top_k, len(ranked)),
        )

        return [candidate for candidate, _ in ranked[:top_k]]


_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker(get_settings().RAG_RERANKER_MODEL)
    return _reranker
