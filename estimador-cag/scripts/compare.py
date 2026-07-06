"""Compara la similitud coseno entre los embeddings de dos textos.

Uso:
    uv run python scripts/compare.py --text-a "..." --text-b "..."
"""

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.embedding_pipeline.embedder import get_embedder  # noqa: E402


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    return dot_product / (norm_a * norm_b)


def main() -> None:
    parser = argparse.ArgumentParser(description="Similitud coseno entre embeddings de dos textos.")
    parser.add_argument("--text-a", required=True, help="Primer texto a comparar.")
    parser.add_argument("--text-b", required=True, help="Segundo texto a comparar.")
    args = parser.parse_args()

    embedder = get_embedder()
    embedding_a = embedder.embed_one(args.text_a)
    embedding_b = embedder.embed_one(args.text_b)
    similarity = cosine_similarity(embedding_a, embedding_b)

    print(f"Text A: {args.text_a}")
    print(f"Text B: {args.text_b}")
    print(f"Cosine similarity: {similarity:.4f}")


if __name__ == "__main__":
    main()
