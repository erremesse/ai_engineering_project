"""Extension pgvector + tablas documents/chunks.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-13

Deliberadamente SIN indice vectorial (HNSW / IVFFlat): el sequential scan es
el baseline contra el que se medira el impacto del indice en el directo. Los
indices no-vectoriales (FK, chunk_type, GIN sobre metadata) si se crean aqui
porque son higiene relacional normal, no el objeto de la demo en vivo.

`ix_documents_source_path` es un indice normal (no-unico), tal cual pide el
enunciado; la unicidad de `source_path` la aplica la comprobacion a nivel de
aplicacion que devuelve 409 (check-then-insert, no a prueba de condiciones
de carrera bajo ingestas concurrentes identicas — aceptable a esta escala).

La dimension del vector se lee de `Settings.EMBEDDING_DIMENSION` en vez de
estar hardcodeada a 1536: el proveedor de embeddings configurado en este
proyecto (Ollama/nomic-embed-text, 768 dims) no es OpenAI, asi que un valor
fijo habria roto la migracion aqui. Cambiar de proveedor tras haber
ingestado datos sigue requiriendo una migracion nueva y re-embeber el
corpus completo — el mismo compromiso que un valor hardcodeado, solo que
parametrizado por variable de entorno en lugar de codigo (ver README).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.config import get_settings

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("source_path", sa.Text, nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("ix_documents_source_path", "documents", ["source_path"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.BigInteger,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        # Nullable: deja la puerta abierta a insertar el chunk y rellenar el
        # vector despues (ingesta asincrona, sesiones futuras). Aqui se
        # escriben chunk+embedding de forma atomica.
        sa.Column("embedding", Vector(get_settings().EMBEDDING_DIMENSION), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_chunk_type", "chunks", ["chunk_type"])
    op.create_index("ix_chunks_metadata_gin", "chunks", ["metadata"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_chunks_metadata_gin", table_name="chunks")
    op.drop_index("ix_chunks_chunk_type", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_source_path", table_name="documents")
    op.drop_table("documents")
    # La extension vector se deja instalada: eliminarla es una operacion a
    # nivel de cluster que podria romper otros objetos, y recrearla es
    # gratis (IF NOT EXISTS) en el siguiente upgrade.
