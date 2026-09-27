"""Persistencia del backend de negocio (Sesion 15): historial de estimaciones.

Base de datos relacional propia (servicio `postgres` en compose), separada de
la BBDD vectorial del servicio IA: cada servicio es dueno de sus datos. El
esquema es una sola tabla y se crea con CREATE TABLE IF NOT EXISTS al arrancar;
con mas tablas convendria un sistema de migraciones (como Alembic en el
servicio IA).

RGPD: input_text guarda la transcripcion tal cual; no introducir datos
personales identificables en las transcripciones.
"""

import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

_SCHEMA = """
CREATE TABLE IF NOT EXISTS estimations (
    id           BIGSERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    mode         TEXT NOT NULL,
    input_text   TEXT NOT NULL,
    result_text  TEXT,
    result_json  JSONB,
    model        TEXT,
    total_tokens INTEGER,
    elapsed_s    DOUBLE PRECISION
)
"""


def connect() -> psycopg.Connection:
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row)
    conn.execute(_SCHEMA)
    return conn


def save_estimation(
    conn: psycopg.Connection,
    *,
    mode: str,
    input_text: str,
    result_text: str | None = None,
    result_json: dict | None = None,
    model: str | None = None,
    total_tokens: int | None = None,
    elapsed_s: float | None = None,
) -> None:
    conn.execute(
        "INSERT INTO estimations (mode, input_text, result_text, result_json, model, total_tokens, elapsed_s) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            mode,
            input_text,
            result_text,
            Jsonb(result_json) if result_json is not None else None,
            model,
            total_tokens if isinstance(total_tokens, int) else None,
            elapsed_s,
        ),
    )


def list_recent(conn: psycopg.Connection, limit: int = 10) -> list[dict]:
    return conn.execute(
        "SELECT id, created_at, mode, input_text, result_text, result_json, model, elapsed_s "
        "FROM estimations ORDER BY created_at DESC LIMIT %s",
        (limit,),
    ).fetchall()
