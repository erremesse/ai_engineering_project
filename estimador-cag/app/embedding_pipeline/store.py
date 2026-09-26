"""Capa de acceso a datos async sobre documents/chunks.

El store nunca abre ni comitea sesiones: quien lo llama (el router) posee la
`AsyncSession`, de forma que una ingesta completa (comprobacion de duplicado,
fila de document, filas de chunks) cabe en UNA transaccion. Un fallo en
cualquier punto revierte todo y no deja documents huerfanos.
"""

from sqlalchemy import Integer, Row, Text, and_, cast, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.embedding_pipeline.models import Chunk, Document
from app.embedding_pipeline.schemas import EmbeddedChunk

BUDGET_COMPONENT = "budget_component"


class ChunkStore:
    async def find_document_id(self, session: AsyncSession, source_path: str) -> int | None:
        stmt = select(Document.id).where(Document.source_path == source_path)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def persist_document_with_chunks(
        self,
        session: AsyncSession,
        *,
        source_path: str,
        document_type: str,
        doc_metadata: dict,
        embedded_chunks: list[EmbeddedChunk],
    ) -> int:
        document = Document(
            source_path=source_path,
            document_type=document_type,
            metadata_=doc_metadata,
        )
        session.add(document)
        await session.flush()  # asigna document.id sin comitear

        session.add_all(
            Chunk(
                document_id=document.id,
                chunk_type=BUDGET_COMPONENT,
                content=chunk.text,
                embedding=chunk.embedding,
                metadata_=chunk.metadata,
            )
            for chunk in embedded_chunks
        )
        return document.id

    async def search(self, session: AsyncSession, *, query_vector: list[float], k: int) -> list[Row]:
        """k chunks mas cercanos por distancia coseno (`<=>`), sequential scan."""
        distance = Chunk.embedding.cosine_distance(query_vector)
        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.chunk_type,
                Chunk.content,
                Chunk.metadata_,
                distance.label("distance"),
            )
            .order_by(distance)
            .limit(k)
        )
        return list((await session.execute(stmt)).all())

    async def search_filtered(
        self,
        session: AsyncSession,
        *,
        query_vector: list[float],
        top_k: int,
        distance_threshold: float,
        sectors: list[str] | None = None,
        project_year_min: int | None = None,
        project_year_max: int | None = None,
        chunk_types: list[str] | None = None,
        tech_stack: list[str] | None = None,
    ) -> list[Row]:
        """Version con threshold + filtros de metadata de `search()`.

        No sustituye a `search()` (sigue siendo el camino simple de Sesion 08); esta
        version la consume el retriever de RAG. `sector`/`year`/`tech_stack` ya vienen
        denormalizados en `chunks.metadata` desde la ingesta (ver `chunker.py`), asi que
        los filtros se aplican directamente ahi, sin JOIN a `documents`. La expresion de
        distancia se calcula una unica vez y se reutiliza en `WHERE` y en `ORDER BY`
        para que Postgres no la evalue dos veces.
        """
        distance = Chunk.embedding.cosine_distance(query_vector)

        conditions = [distance < distance_threshold]
        if sectors:
            conditions.append(Chunk.metadata_["client_sector"].astext.in_(sectors))
        if project_year_min is not None:
            conditions.append(Chunk.metadata_["year"].astext.cast(Integer) >= project_year_min)
        if project_year_max is not None:
            conditions.append(Chunk.metadata_["year"].astext.cast(Integer) <= project_year_max)
        if chunk_types:
            conditions.append(Chunk.chunk_type.in_(chunk_types))
        if tech_stack:
            conditions.append(Chunk.metadata_["tech_stack"].op("?|")(cast(tech_stack, ARRAY(Text))))

        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.chunk_type,
                Chunk.content,
                Chunk.metadata_,
                distance.label("distance"),
            )
            .where(and_(*conditions))
            .order_by(distance)
            .limit(top_k)
        )
        return list((await session.execute(stmt)).all())
