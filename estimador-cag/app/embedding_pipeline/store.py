"""Capa de acceso a datos async sobre documents/chunks.

El store nunca abre ni comitea sesiones: quien lo llama (el router) posee la
`AsyncSession`, de forma que una ingesta completa (comprobacion de duplicado,
fila de document, filas de chunks) cabe en UNA transaccion. Un fallo en
cualquier punto revierte todo y no deja documents huerfanos.
"""

from sqlalchemy import Row, select
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
