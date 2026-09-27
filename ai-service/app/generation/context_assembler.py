"""Ensamblado del bloque de contexto que se pasa al generador.

Los chunks van delimitados con XML (`<source ...>`) porque los LLM modernos
reconocen esas etiquetas como limites semanticos, y llevan la metadata como
atributos para que el generador pueda citar `source id` sin adivinar nada.
"""

import tiktoken

from app.retrieval.schemas import RetrievedChunk

# Mismo tokenizer que `embedding_pipeline.chunker`, usado aqui solo como proxy de
# tamano para el presupuesto de contexto (independiente del proveedor de generacion).
_TOKENIZER_MODEL = "text-embedding-3-small"


def _wrap_chunk(chunk: RetrievedChunk) -> str:
    attrs = " ".join(
        [
            f'id="{chunk.id}"',
            f'sector="{chunk.sector or "unknown"}"',
            f'project_year="{chunk.project_year or "unknown"}"',
            f'chunk_type="{chunk.chunk_type}"',
            # None para chunks que solo vinieron de la rama lexica de una
            # busqueda hibrida (sin distancia coseno propia, ver retriever.py).
            f'distance="{chunk.distance:.3f}"' if chunk.distance is not None else 'distance="n/a"',
        ]
    )
    return f"<source {attrs}>\n{chunk.content.strip()}\n</source>"


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(_wrap_chunk(chunk) for chunk in chunks)


def truncate_to_token_budget(chunks: list[RetrievedChunk], max_context_tokens: int) -> list[RetrievedChunk]:
    """Descarta chunks completos (nunca los parte) hasta caber en el presupuesto.

    Los chunks deben venir ya ordenados por relevancia (distancia ascendente): el
    primero en no caber corta la lista, no se sigue buscando uno mas pequeno mas
    adelante.
    """
    encoder = tiktoken.encoding_for_model(_TOKENIZER_MODEL)
    selected: list[RetrievedChunk] = []
    used_tokens = 0
    for chunk in chunks:
        wrapped_size = len(encoder.encode(_wrap_chunk(chunk)))
        if used_tokens + wrapped_size > max_context_tokens:
            break
        selected.append(chunk)
        used_tokens += wrapped_size
    return selected


def reorder_u_pattern(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Mitigacion opcional de 'lost in the middle' para K altos (15-20+).

    No se activa por defecto: con K=5-10 (el rango habitual de este proyecto) el
    efecto es modesto y los chunks mas relevantes ya quedan en las posiciones
    privilegiadas del principio con el orden simple por distancia ascendente.
    """
    front, back = [], []
    for i, chunk in enumerate(chunks):
        (front if i % 2 == 0 else back).append(chunk)
    return front + list(reversed(back))
