#!/bin/sh
# Applies Alembic migrations (pgvector extension + documents/chunks + FTS) before
# starting the server, so `docker compose up` needs no manual step. Idempotent:
# a restart with an up-to-date schema is a no-op.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] applying database migrations..."
    alembic upgrade head
    echo "[entrypoint] migrations up to date."
else
    echo "[entrypoint] RUN_MIGRATIONS=false - skipping alembic."
fi

exec "$@"
