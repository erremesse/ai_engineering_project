# Estimador CAG

Software project estimation service powered by LLMs. A FastAPI backend generates structured effort estimations from project descriptions using CAG (Context-Augmented Generation) with few-shot examples, plus a RAG pipeline (Session 09) that turns a raw meeting transcript into a source-grounded, structured estimate over historical budgets persisted in pgvector. A Streamlit frontend provides transactional (single-shot), conversational (multi-turn), and RAG-from-transcript interfaces, with file attachment support in the conversational mode.

## Stack

- **Python 3.11+** / **FastAPI** / **Uvicorn**
- **Streamlit** — web frontend with transactional and conversational modes
- **LiteLLM Router** — provider aggregator with automatic fallback chain
- **Pydantic v2 + Pydantic Settings** for schemas and configuration
- **pypdf / python-docx** — local text extraction from PDF and Word attachments (Camino B)
- **PostgreSQL + pgvector** (`pgvector/pgvector:pg16`) — vector persistence, via **SQLAlchemy 2.0** (async, `asyncpg`) and **Alembic** migrations

### Supported providers

| Provider | Default model | When used |
| --- | --- | --- |
| Anthropic | `claude-haiku-4-5` | Primary when `LLM_PROVIDER=anthropic` |
| OpenAI | `gpt-4o-mini` | Primary when `LLM_PROVIDER=openai` |
| Ollama | configurable | Primary when `LLM_PROVIDER=ollama`; remote server via `OLLAMA_API_BASE` |

The router tries the configured primary provider first, then falls back to the others automatically.

## Setup

```bash
# Install dependencies
uv pip install -e .

# Configure environment
cp .env.example .env
# Edit .env — set at least one of ANTHROPIC_API_KEY / OPENAI_API_KEY, or OLLAMA_API_BASE
```

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_PROVIDER` | `anthropic` | Primary provider: `anthropic`, `openai`, or `ollama` |
| `ANTHROPIC_API_KEY` | — | Anthropic API key (required if using Anthropic) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | Anthropic model identifier |
| `OPENAI_API_KEY` | — | OpenAI API key (required if using OpenAI) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model identifier |
| `OLLAMA_API_BASE` | — | Base URL for Ollama server, e.g. `http://host:11434` |
| `OLLAMA_MODELS` | `llama3.3:70b,deepseek-r1:70b` | Comma-separated list of Ollama models (first is primary) |
| `EMBEDDING_PROVIDER` | `openai` | Embeddings backend: `openai` (`text-embedding-3-small`) or `ollama` (local/remote model) |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model name, used when `EMBEDDING_PROVIDER=ollama` (served by `OLLAMA_API_BASE`) |
| `EMBEDDING_DIMENSION` | `1536` | Dimension of the configured embedding model — must be kept in sync manually: `1536` for `text-embedding-3-small`, `768` for `nomic-embed-text` (see [Decisiones de schema](#decisiones-de-schema-sesión-08)) |
| `DATABASE_URL` | `postgresql+asyncpg://estimator:estimator@localhost:5432/estimator` | Async Postgres connection string (pgvector persistence). Overridden by `docker-compose.yml` to the in-network host |
| `NUM_CAG_EXAMPLES` | `5` | Default number of few-shot examples injected into the prompt |
| `APP_ENV` | `development` | Runtime environment |
| `LOG_LEVEL` | `DEBUG` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ESTIMADOR_API_BASE` | `http://localhost:8000` | Base URL of the FastAPI server, consumed by Streamlit (host perspective) |
| `RETRIEVAL_API_KEY` | — (unset) | `X-API-Key` required on `POST /v1/retrieval/search`. Leave unset in local dev to disable auth on this route (see [RAG pipeline design decisions](#rag-pipeline-design-decisions-sesión-09)) |
| `ESTIMATE_API_KEY` | — (unset) | `X-API-Key` required on `POST /v1/estimate/from-transcript`. Also read directly by `streamlit_app.py` (`os.getenv`, not loaded from `.env`) to call that endpoint |
| `RAG_TOP_K` | `10` | Default number of chunks retrieved per RAG query, before `RAG_DISTANCE_THRESHOLD` trims them |
| `RAG_DISTANCE_THRESHOLD` | `0.6` | Cosine distance cutoff (pgvector `<=>`, 0–2 scale) — chunks above this are discarded, not just ranked lower |
| `RAG_MAX_CONTEXT_TOKENS` | `4000` | Token budget for the context block passed to the generator; whole chunks are dropped, never split, once the budget is exceeded |

> **Migration note:** the old `ESTIMADOR_API_URL` variable (full path) has been replaced by `ESTIMADOR_API_BASE` (base URL only). Update your `.env` if you had it set explicitly.

## Run

### With Docker (recommended — includes Postgres + pgvector)

```bash
docker compose up -d
docker compose run --rm ai_service alembic upgrade head   # first run only
```

- API docs: `http://localhost:8000/docs`
- Postgres: `localhost:5432` (`estimator` / `estimator` / `estimator`)

### Locally (no Postgres — `/embeddings/ingest` and `/search` need it)

```bash
# Start FastAPI backend
uvicorn app.main:app --reload

# Start Streamlit frontend (separate terminal)
streamlit run streamlit_app.py
```

- API docs: `http://localhost:8000/docs`
- Streamlit UI: `http://localhost:8501`

## API endpoints

### Transactional (single-shot, no session)

#### `POST /api/v1/estimate`

Generates an effort estimation (blocking).

#### Request

```json
{
  "description": "We need a mobile app with login, user profiles, and push notifications...",
  "project_type": "mobile_app",
  "detail_level": "medium",
  "output_format": "phases_table",
  "n_examples": 3
}
```

| Field | Type | Values |
| --- | --- | --- |
| `description` | `string` | 20–2000 characters |
| `project_type` | enum | `mobile_app`, `web_saas`, `internal_tool`, `data_pipeline` |
| `detail_level` | enum | `summary`, `medium`, `detailed` |
| `output_format` | enum | `phases_table`, `line_items`, `narrative` |
| `n_examples` | `int \| null` | ≥ 1; defaults to `NUM_CAG_EXAMPLES` |

#### Response

```json
{
  "text": "## Estimation\n\n| Phase | Description | Hours | Cost (EUR) |\n...",
  "prompt_version": "v1",
  "model": "claude-haiku-4-5-20251001",
  "provider": "anthropic",
  "usage": { "input_tokens": 1842, "output_tokens": 512, "total_tokens": 2354 }
}
```

#### `POST /api/v1/estimate/stream`

Same request body as above. Returns a plain-text stream of tokens. The final chunk is prefixed with `\x00` and contains a JSON object with `model`, `input_tokens`, `output_tokens`, and `total_tokens`.

---

### Conversational (multi-turn, with session)

#### `POST /api/v1/sessions`

Creates a new empty session. Returns `{"session_id": "<uuid4>"}` (HTTP 201).

#### `GET /api/v1/sessions/{session_id}`

Returns the current session state (useful for debugging):

```json
{
  "session_id": "...",
  "turn_count": 2,
  "metadata": {
    "project_name": "Portal RR.HH.",
    "assumed_team_size": 3,
    "mentioned_technologies": ["react", "fastapi", "postgresql"],
    "agreed_scope": "Aplicacion web interna para gestion de..."
  }
}
```

#### `POST /api/v1/sessions/{session_id}/estimate`

Multi-turn estimation endpoint. Accepts `multipart/form-data`:

| Field | Type | Description |
| --- | --- | --- |
| `transcript` | `string` (Form) | Project description or turn text (20–2000 chars) |
| `project_type` | enum (Form) | Same values as transactional endpoint |
| `detail_level` | enum (Form) | Same values as transactional endpoint |
| `output_format` | enum (Form) | Same values as transactional endpoint |
| `n_examples` | `int` (Form, optional) | Number of CAG examples |
| `attachments` | `UploadFile[]` (File, optional) | PDF or DOCX files |

The response extends the transactional response with session state:

```json
{
  "text": "...",
  "prompt_version": "v1",
  "model": "claude-haiku-4-5-20251001",
  "provider": "anthropic",
  "usage": { "input_tokens": 2100, "output_tokens": 640, "total_tokens": 2740 },
  "session_id": "...",
  "turn_count": 2,
  "metadata": { ... }
}
```

---

### `GET /health`

Returns `{"status": "healthy"}`.

---

### Embeddings and semantic search (Session 08 — pgvector persistence)

Historical budgets are split into chunks (one component = one chunk), embedded, and
persisted in PostgreSQL + pgvector. Session 07 returned vectors over HTTP without
persisting anything; **since Session 08 `/embeddings/ingest` persists to the database**
and `/search` runs real semantic retrieval against it.

#### `POST /embeddings/ingest`

One request ingests **one document** (one historical budget) — chunk → embed → persist,
all inside a single async transaction. If the embeddings call fails, the whole transaction
rolls back: no orphan `documents` row survives.

##### Ingest request body

```json
{
  "source_path": "data/budgets_sample.json::BUD-2024-001",
  "document_type": "historical_budget",
  "content": { /* one budget object, same schema as data/budgets_sample.json items */ }
}
```

##### Ingest response body

```json
{
  "document_id": 1,
  "chunks_created": 4,
  "embedding_dimension": 768,
  "ingestion_time_ms": 1240
}
```

`embedding_dimension` reflects `EMBEDDING_DIMENSION` (see [Decisiones de schema](#decisiones-de-schema-sesión-08) below) — `1536` with `EMBEDDING_PROVIDER=openai` (`text-embedding-3-small`), `768` with `EMBEDDING_PROVIDER=ollama` (`nomic-embed-text`).

Token/cost stats (`total_tokens`, `estimated_cost_usd`) no longer travel in the HTTP
response — the exercise's response contract is fixed to the four fields above — but they
are not lost: they land in the `embedding_ingest_completed` structured log event.

Status codes:

| Code | Meaning |
| --- | --- |
| `200` | Ingested successfully. |
| `409` | A document with the same `source_path` already exists: `{"detail": "Document already ingested", "document_id": 42}`. |
| `422` | Pydantic validation error (malformed budget JSON). |
| `500` | Embeddings backend call failed (generic message to the client, full detail in the logs). |

#### `POST /search`

Embeds the query with the same model used at ingest time and ranks chunks by cosine
distance (`<=>` operator) via SQL — no vector index yet (see below), so this is a
sequential scan.

##### Search request body

```json
{ "query": "REST API with OAuth authentication for fintech sector", "k": 5 }
```

##### Search response body

```json
{
  "query": "REST API with OAuth authentication for fintech sector",
  "k": 5,
  "search_time_ms": 87,
  "results": [
    {
      "chunk_id": 1,
      "document_id": 1,
      "chunk_type": "budget_component",
      "content": "[Project: Mobile banking API...]\n\nComponent: OAuth 2.0 authentication backend...",
      "distance": 0.2851,
      "metadata": { "budget_id": "BUD-2024-001", "client_sector": "finance", "complexity": "high" }
    }
  ]
}
```

#### `scripts/query_examples.py` — semantic search smoke test

Replaces Session 07's `compare.py` (which measured similarity between two loose texts).
Instead it exercises the real retrieval path over HTTP: ingests `data/budgets_sample.json`
(one document per budget, idempotent — already-ingested documents answer `409` and are
skipped) and then runs five queries that probe the corpus from different angles (direct
match, semantic reformulation, out-of-domain, ambiguous, highly specific).

```bash
docker compose up -d
docker compose run --rm ai_service python scripts/query_examples.py
```

The real output against the sample corpus (15 budgets, `EMBEDDING_PROVIDER=ollama`) is in
[`output_examples.txt`](output_examples.txt).

### Decisiones de schema (Sesión 08)

Dos tablas gestionadas con Alembic (`alembic/versions/0001_initial_schema.py`):
`documents` (procedencia: `source_path`, `document_type`, `ingested_at`, `metadata` JSONB)
y `chunks` (`content`, `embedding vector`, `metadata` JSONB), con `ON DELETE CASCADE`.

- **Dos tablas y no una.** Un presupuesto produce N chunks: es un uno-a-muchos real. Una
  tabla única duplicaría la metadata del documento en cada fila y perdería integridad
  referencial. Con `ON DELETE CASCADE`, borrar un presupuesto elimina automáticamente
  todos sus chunks.
- **`metadata` como JSONB y no columnas tipadas.** Lo estable (tipo de documento, tipo de
  chunk, fechas) va en columnas tipadas; lo que el chunker puede enriquecer (sector,
  tecnologías, horas estimadas) va a JSONB. El índice GIN (`ix_chunks_metadata_gin`)
  permite consultar por claves arbitrarias sin una migración por cada clave nueva.
- **`cosine_distance` y no L2 ni inner product.** Los embeddings vienen normalizados
  (tanto `text-embedding-3-small` como `nomic-embed-text`), así que el ranking sería
  equivalente con cualquiera de los tres; usamos coseno por convención de la literatura
  RAG y, sobre todo, para quedar alineados con la operator class `vector_cosine_ops` del
  índice HNSW que se añadirá en el directo — si la query usa un operador y el índice está
  construido con otra operator class, Postgres ignora el índice **en silencio** y cae a
  sequential scan.
- **Sin índice vectorial todavía (deliberado).** El sequential scan es el baseline contra
  el que el directo mide el impacto de HNSW/IVFFlat. Añadirlo ahora ocultaría justamente
  lo que se quiere observar en vivo.
- **`embedding` nullable.** Permite insertar el chunk y rellenar el vector después
  (ingesta asíncrona, sesiones futuras). Aquí chunk + embedding se escriben de forma
  atómica en una sola transacción.
- **`vector(EMBEDDING_DIMENSION)` configurable, no `vector(1536)` hardcodeado.** El
  enunciado pide hardcodear la dimensionalidad de `text-embedding-3-small` (1536), pero
  este proyecto ya traía `EMBEDDING_PROVIDER=ollama` (`nomic-embed-text`, 768 dims)
  configurado desde la Sesión 07 sin una `OPENAI_API_KEY` real disponible. Hardcodear 1536
  habría roto la migración contra el proveedor realmente configurado. En su lugar,
  `Settings.EMBEDDING_DIMENSION` (leída en `app/embedding_pipeline/models.py` y en la
  migración) fija la dimensión según el proveedor activo — **desviación deliberada del
  enunciado**, documentada aquí en vez de escondida. La compensación no es gratis: cambiar
  de proveedor sigue exigiendo una migración nueva y re-embeber todo el corpus, exactamente
  igual que con un valor hardcodeado; solo cambia dónde vive el número (variable de
  entorno vs. código).

**Fuera de scope (se construye en el directo):** índices vectoriales (HNSW/IVFFlat),
filtros por metadata en SQL, búsqueda híbrida (full-text + vector) y tuning de Postgres
(`shared_buffers`, `maintenance_work_mem`, `ef_search`).

### RAG pipeline: transcript → estimate (Sesión 09)

Session 08 stopped at persistence and raw retrieval: `/search` returns chunks, nothing
turns them into an estimate. Session 09 closes that loop with two new endpoints under
`app/api/`, on top of `app/retrieval/` (query reformulation + filtered retriever) and
`app/generation/` (context assembly + structured generation) — none of the Session 06-08
modules (`embedding_pipeline/*`, `prompts/*`) were modified, only extended additively
(see [design decisions](#rag-pipeline-design-decisions-sesión-09) below).

Both endpoints require an `X-API-Key` header (`RETRIEVAL_API_KEY` / `ESTIMATE_API_KEY`);
auth is skipped with a logged warning if the corresponding variable is unset (local-dev
convenience, same posture as every other endpoint in this project today).

#### `POST /v1/retrieval/search`

Low-level endpoint: runs the filtered vector search directly against pgvector, without
going through transcript reformulation. Useful to debug retrieval in isolation.

```json
{
  "query_text": "telemedicine video consultation with waiting room",
  "top_k": 10,
  "distance_threshold": 0.6,
  "sectors": ["healthcare"],
  "project_year_min": 2023,
  "chunk_types": ["budget_component"],
  "tech_stack": ["python_django"]
}
```

```json
{
  "chunks": [
    { "id": 32, "content": "...", "sector": "healthcare", "project_year": 2024, "chunk_type": "budget_component", "distance": 0.386 }
  ],
  "low_confidence": false,
  "total_candidates_considered": 10
}
```

`low_confidence: true` (with an empty `chunks` list) means no chunk cleared
`distance_threshold` — a deliberate soft-fail, not an error.

#### `POST /v1/estimate/from-transcript`

Orchestrates the full pipeline: reformulation → retrieval → context assembly →
generation → citation validation, each stage logged separately via `structlog`
(`stage.started` / `stage.completed` / `stage.failed`, `duration_ms`).

```json
{
  "transcript": "<raw meeting transcript, 100-50000 chars>",
  "idempotency_key": "optional-client-supplied-id"
}
```

```json
{
  "total_engineer_days": 350,
  "cost_breakdown": [
    { "name": "Telemedicine video sessions", "engineer_days": 20, "sources": [32] }
  ],
  "duration_weeks": 10,
  "sources": [
    { "source_id": 32, "relevance": "primary", "used_for": "Telemedicine video sessions" }
  ],
  "assumptions": [
    { "description": "No existing EHR integration assumed", "impact": "medium", "rationale": "..." }
  ],
  "confidence": "medium",
  "reasoning": "...",
  "insufficient_context_explanation": null
}
```

If retrieval comes back `low_confidence` (nothing in the corpus is close enough to the
transcript), the endpoint returns `confidence: "insufficient"` directly — **the generator
is never called with empty context**, which is what would invite hallucination. Any
`source_id` the generator cites that was not actually retrieved is stripped before the
response is returned (`validate_citations`, logged as `citation_validation_failed`).

`idempotency_key` is accepted and bound into the structured logs for traceability; there
is no deduplication/persistence behind it yet in this session's scope.

### RAG pipeline design decisions (Sesión 09)

- **Extracción estructurada (`EstimationQuery`) y no HyDE ni query rewriting puro.**
  Coste/latencia comparables a HyDE (una sola llamada al LLM antes de la búsqueda), pero
  produce un artefacto inspeccionable — se puede ver exactamente qué entendió el
  reformulador — y, sobre todo, alimenta los filtros de metadata del retriever además del
  texto embebido. Si la extracción estructurada falla (proveedor sin soporte de
  `json_schema` estricto, o transcripción genuinamente ambigua), cae a un rewrite libre
  más simple (`reformulation_fallback` en los logs); si ese porcentaje supera el ~5% de
  las llamadas, es señal de un problema sistemático con el prompt o el esquema, no de
  transcripciones raras sueltas.
- **`response_format=<PydanticModel>` sobre el `litellm.Router` existente, no la Responses
  API de OpenAI directamente.** El proyecto ya tenía un único punto de acceso multi-
  proveedor (`app/services/llm_router.py`, Anthropic/OpenAI/Ollama con fallback); duplicar
  ese acceso solo para RAG habría introducido una segunda forma de hablar con LLMs en el
  mismo repo. La contrapartida: con `LLM_PROVIDER=ollama` (configuración real de este
  repo) el modelo primario puede no soportar `json_schema` estricto de forma nativa —
  `litellm.drop_params=True` lo descarta en silencio — por lo que `generate_structured`
  reintenta sin `response_format`, reforzando el esquema en el propio prompt, antes de
  propagar el error. Para máxima fiabilidad en pruebas de este pipeline, usa
  `LLM_PROVIDER=openai` o `anthropic`.
- **Filtros de metadata sobre `chunks`, sin `JOIN` a `documents`.** `client_sector` y
  `year` ya venían denormalizados en `chunks.metadata` desde el chunker de Sesión 07;
  Sesión 09 añade `tech_stack` al mismo nivel (`app/embedding_pipeline/chunker.py`). El
  filtro de `tech_stack` usa el operador `?|` de `jsonb` (overlap), lo que requiere
  Postgres ≥ 14 (el compose usa `pg16`, sin problema) — y como la ingesta es idempotente
  por `source_path`, el corpus de ejemplo ya ingerido necesita un vaciado + re-ingesta
  (`scripts/query_examples.py`) para que sus chunks tengan `tech_stack` en la metadata.
- **Soft-fail en retrieval, no en generación.** Si ningún chunk supera
  `RAG_DISTANCE_THRESHOLD`, el orquestador nunca llama al generador — devuelve
  `confidence: "insufficient"` directamente. Alimentar al generador con contexto vacío
  solo invita a alucinar una estimación con apariencia de solidez.
- **Truncamiento por chunk completo, nunca parcial.** `truncate_to_token_budget` descarta
  el chunk entero si no cabe en `RAG_MAX_CONTEXT_TOKENS`; un chunk cortado a mitad no solo
  pierde coherencia semántica, también generaría citas a un `source_id` cuya evidencia
  real el modelo nunca vio completa.
- **API keys opcionales, no obligatorias.** Si `RETRIEVAL_API_KEY`/`ESTIMATE_API_KEY` no
  están configuradas, la comprobación se salta con un warning logueado — mismo criterio
  que el resto de endpoints del proyecto (ninguno tiene auth todavía). Es una decisión de
  conveniencia para desarrollo local, no el valor por defecto recomendado en producción.

**Fuera de scope (Sesión 10, en otra rama):** hybrid search (full-text + vector con RRF)
y reranking con cross-encoder — el retriever de esta sesión es puramente vectorial.

## Conversational memory design

### Sliding window

The service keeps the last `MAX_TURNS = 6` user/assistant pairs per session (configurable). Older turns are discarded when the limit is exceeded. The system prompt is regenerated on every turn to reflect the latest `project_metadata`, so it is never stored as part of the history.

### project_metadata

A separate `ProjectMetadata` object accumulates facts about the project across turns, independent of the message history:

| Field | How it is populated |
| --- | --- |
| `project_name` | First regex match on the user transcript (immutable once set) |
| `assumed_team_size` | First numeric mention of team size (immutable once set) |
| `mentioned_technologies` | Cumulative union across all turns |
| `agreed_scope` | First 400 chars of the first user transcript (immutable once set) |

**Extraction strategy: heurística simple (regex).** A second LLM call per turn was considered but rejected: it adds latency and token cost with limited benefit at this stage. The heuristic is cheaper, predictable, and sufficient for the current phase. A LLM-based extractor would be the next step if precision becomes a bottleneck.

### Session storage

Sessions are stored in an in-memory dictionary (`SessionStore`). There is no database or Redis backend. **Sessions are lost on server restart.** This is an accepted trade-off for this phase: the goal is to explore conversational patterns, not to build a production-grade persistence layer.

## File attachments (Camino B — local extraction)

PDF and DOCX files uploaded via `attachments` are processed locally before the LLM call:

- **PDF** — text extracted page by page with `pypdf`.
- **DOCX** — paragraphs extracted with `python-docx`.

Each attachment is appended to the user message with a clear separator:

```text
--- attachment: spec.pdf ---
<extracted text>
```

**Why Camino B instead of Camino A (Files API)?**

- Provider-agnostic: works with any LLM in the router, not just multimodal ones.
- No per-file token overhead from binary encoding.
- Prepares the ground for chunking and RAG in future phases.

## Project structure

```text
estimador-cag/
├── app/
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # Settings (Pydantic Settings + .env)
│   ├── db/
│   │   ├── base.py                  # Declarative Base shared by all ORM models
│   │   └── session.py               # Async engine, session factory, get_session dependency
│   ├── routers/
│   │   ├── estimations.py           # /estimate and /estimate/stream (transactional)
│   │   └── sessions.py              # /sessions and /sessions/{id}/estimate (conversational)
│   ├── api/                         # Session 09 — RAG endpoints, kept apart from routers/
│   │   ├── security.py              # require_retrieval_key / require_estimate_key (X-API-Key)
│   │   └── routers/
│   │       ├── retrieval.py         # POST /v1/retrieval/search
│   │       └── estimate.py          # POST /v1/estimate/from-transcript
│   ├── retrieval/                   # Session 09 — query reformulation + filtered retriever
│   │   ├── schemas.py               # EstimationQuery, RetrievedChunk, RetrievalResult
│   │   ├── query_reformulator.py    # reformulate() (structured extraction + rewrite fallback)
│   │   └── retriever.py             # search_chunks() — top-K/threshold/metadata filters
│   ├── generation/                  # Session 09 — context assembly + structured generation
│   │   ├── schemas.py               # Estimate, CostComponent, SourceCitation, Assumption
│   │   ├── context_assembler.py     # build_context_block, truncate_to_token_budget, reorder_u_pattern
│   │   ├── prompt_builder.py        # ESTIMATOR_SYSTEM_PROMPT, build_user_prompt
│   │   ├── observability.py         # log_stage context manager (per-stage structlog events)
│   │   └── estimator.py             # estimate_from_transcript() orchestrator, validate_citations
│   ├── schemas/
│   │   ├── estimation.py            # Transactional request/response models and enums
│   │   └── sessions.py              # Session response models
│   ├── services/
│   │   ├── llm_router.py            # LiteLLM Router configuration and provider helpers
│   │   ├── llm_service.py           # generate_estimation, stream_estimation, generate_from_messages, generate_structured
│   │   ├── cache.py                 # ExactMatchCache (SHA-256, TTL-based)
│   │   └── attachment_service.py    # PDF/DOCX text extraction (AttachmentService)
│   ├── sessions/
│   │   ├── models.py                # ProjectMetadata, ConversationHistory, Session
│   │   ├── store.py                 # SessionStore (in-memory singleton)
│   │   ├── metadata.py              # MetadataExtractor (heuristic, regex-based)
│   │   └── __init__.py              # Public re-exports
│   ├── prompts/
│   │   ├── loader.py                # render_estimation_prompt, render_session_prompt
│   │   └── estimation/v1/
│   │       ├── system.j2            # System prompt (with optional project_context block)
│   │       ├── user.j2              # User prompt wrapper
│   │       └── examples.j2          # CAG examples formatter
│   ├── context/
│   │   └── examples.py              # Five few-shot CAG examples
│   └── embedding_pipeline/
│       ├── schemas.py               # Budget, Chunk, EmbeddedChunk, Ingest/Search request/response models
│       ├── chunker.py                # JSONStructuralChunker — one budget component = one chunk
│       ├── embedder.py               # Embedder (OpenAI / Ollama), get_embedder() factory
│       ├── models.py                 # Document, Chunk ORM models (pgvector)
│       ├── store.py                  # ChunkStore — async repository (find/persist/search/search_filtered)
│       ├── router.py                  # POST /embeddings/ingest, POST /search
│       └── SANITY_CHECK.md           # Cosine similarity results for the 3 validation pairs (Session 07)
├── alembic/
│   ├── env.py                        # Reads DATABASE_URL from Settings, registers the vector type
│   └── versions/
│       └── 0001_initial_schema.py    # CREATE EXTENSION vector + documents/chunks tables
├── alembic.ini
├── Dockerfile                         # ai_service image (uv + uvicorn)
├── docker-compose.yml                 # postgres (pgvector/pgvector:pg16) + ai_service
├── scripts/
│   └── query_examples.py             # CLI: ingests the sample corpus, runs 5 semantic search queries
├── data/
│   └── budgets_sample.json           # 15 sample historical budgets used by embedding_pipeline
├── output_examples.txt               # Real output of query_examples.py against the sample corpus
├── tests/
│   ├── cache/
│   │   └── test_exact_match.py      # Unit tests for ExactMatchCache
│   ├── prompts/
│   │   └── test_estimation_v1.py    # Unit tests for prompt templates
│   ├── retrieval/
│   │   └── test_query_reformulator.py  # compose_search_text + structured/rewrite fallback
│   └── generation/
│       ├── test_context_assembler.py   # XML wrapping, whole-chunk truncation, U-pattern reorder
│       └── test_estimator.py           # validate_citations (pure id comparison)
├── streamlit_app.py                 # Streamlit frontend (transactional + conversational + RAG-from-transcript modes)
└── pyproject.toml
```

## Security note

LiteLLM versions `1.82.7` and `1.82.8` are excluded in `pyproject.toml` due to a supply-chain compromise detected in March 2026. The constraint is `litellm>=1.34.0,!=1.82.7,!=1.82.8`.
