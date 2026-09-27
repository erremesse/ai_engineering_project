"""Full-text search column + GIN index on chunks (Session 10 — hybrid search).

Revision ID: 0002_session10_fulltext_search
Revises: 0001_initial_schema
Create Date: 2026-09-27

`content_tsv` is a generated column (`GENERATED ALWAYS AS ... STORED`), kept in
sync by Postgres itself whenever `content` changes — no application code writes
to it, and `sa.Computed(...)` tells SQLAlchemy to exclude it from INSERT/UPDATE
statements automatically.

Text search configuration: `spanish`, matching the language this system is
actually operated in, not the language of the current sample dataset. As of
this migration, `data/budgets_sample.json` (and the chunk template in
`app/embedding_pipeline/chunker.py`) happens to be entirely in English — a
placeholder corpus, not production content. Real historical budgets ingested
by this system are expected to be Spanish, so `spanish` is the config that will
actually be correct once real data lands, even though it under-stems the
current English sample corpus (Spanish stopwords/stemming mostly no-op on
English text, similar to how untranslatable technical terms pass through
almost intact — see README). This is the same kind of explicit, documented
deviation already used in `0001_initial_schema` (embedding dimension read from
`Settings` instead of hardcoded): choosing correctness for the real target
over correctness for today's placeholder fixture.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_session10_fulltext_search"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column(
            "content_tsv",
            postgresql.TSVECTOR,
            sa.Computed("to_tsvector('spanish', content)", persisted=True),
            nullable=True,
        ),
    )
    op.create_index("ix_chunks_content_tsv", "chunks", ["content_tsv"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_chunks_content_tsv", table_name="chunks")
    op.drop_column("chunks", "content_tsv")
