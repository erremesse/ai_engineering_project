"""Entorno de migraciones Alembic (async).

La URL de conexion se lee de `app.config.Settings` (no de alembic.ini), asi el
contenedor y el host usan la misma fuente de verdad. Los modelos se descubren
importando `app.embedding_pipeline.models`, que registra sus tablas contra
`Base.metadata`.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from pgvector.sqlalchemy import Vector
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.db.base import Base
import app.embedding_pipeline.models  # noqa: F401 — registra las tablas en Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    # Ensena a la reflexion el tipo `vector`. Sin esto, `alembic check` /
    # autogenerate contra una BD que ya tiene columnas vector no puede
    # mapearlas de vuelta y produce diffs inconsistentes.
    connection.dialect.ischema_names["vector"] = Vector
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
