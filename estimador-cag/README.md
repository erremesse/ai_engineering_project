# Estimador CAG

Software project estimation service powered by LLMs. A FastAPI backend generates structured effort estimations from project descriptions using CAG (Context-Augmented Generation) with few-shot examples. A Streamlit frontend provides both a transactional (single-shot) and a conversational (multi-turn) interface with file attachment support.

## Stack

- **Python 3.11+** / **FastAPI** / **Uvicorn**
- **Streamlit** — web frontend with transactional and conversational modes
- **LiteLLM Router** — provider aggregator with automatic fallback chain
- **Pydantic v2 + Pydantic Settings** for schemas and configuration
- **pypdf / python-docx** — local text extraction from PDF and Word attachments (Camino B)

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
| `NUM_CAG_EXAMPLES` | `5` | Default number of few-shot examples injected into the prompt |
| `APP_ENV` | `development` | Runtime environment |
| `LOG_LEVEL` | `DEBUG` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ESTIMADOR_API_BASE` | `http://localhost:8000` | Base URL of the FastAPI server, consumed by Streamlit |

> **Migration note:** the old `ESTIMADOR_API_URL` variable (full path) has been replaced by `ESTIMADOR_API_BASE` (base URL only). Update your `.env` if you had it set explicitly.

## Run

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

### Embeddings

#### `POST /embeddings/ingest`

Splits historical budgets into chunks (one component = one chunk) and generates embeddings
for each of them. Vectors are returned in the response — nothing is persisted yet (that
lands in Session 08 with PostgreSQL + pgvector).

##### Ingest request body

```json
{
  "budgets": [ /* array of budgets, same schema as data/budgets_sample.json */ ]
}
```

##### Ingest response body

```json
{
  "chunks": [
    {
      "chunk_id": "BUD-2024-001::AUTH-001",
      "text": "[Project: Mobile banking API...]\n[Client sector: finance | Year: 2024 | Main tech: ruby_on_rails]\n\nComponent: OAuth 2.0 authentication backend\n...",
      "metadata": {
        "budget_id": "BUD-2024-001",
        "component_id": "AUTH-001",
        "client_sector": "finance",
        "main_technology": "ruby_on_rails",
        "year": 2024,
        "complexity": "high",
        "estimated_hours": 120
      },
      "token_count": 106,
      "embedding": [0.0123, -0.0456, "... 1536 floats with OpenAI / 768 with nomic-embed-text ..."]
    }
  ],
  "stats": {
    "total_budgets": 1,
    "total_chunks": 4,
    "total_tokens": 480,
    "estimated_cost_usd": 0.0000096
  }
}
```

`estimated_cost_usd` is always `0.0` when `EMBEDDING_PROVIDER=ollama` (local/self-hosted model).

Status codes: `200` on success, `422` on Pydantic validation errors, `500` if the embeddings
backend call fails (generic message to the client, full detail in the logs).

#### `scripts/compare.py` — embedding sanity check CLI

Standalone script that embeds two texts and prints their cosine similarity (computed by
hand — no `numpy`/`scikit-learn`). It reuses the same `Embedder` configured via
`EMBEDDING_PROVIDER`.

```bash
# Locally, with .env loaded (project has no Docker setup yet — see note below)
uv run python scripts/compare.py --text-a "OAuth 2.0 authentication backend for fintech" --text-b "JWT-based authorization service for banking app"
```

```text
Text A: OAuth 2.0 authentication backend for fintech
Text B: JWT-based authorization service for banking app
Cosine similarity: 0.6979
```

> **Docker note:** this project currently runs locally via `uv`/`uvicorn` (no `Dockerfile` /
> `docker-compose.yml` yet). Containerizing the service — and adding the equivalent
> `docker compose exec servicio_ia python scripts/compare.py ...` invocation — is pending
> future work.

Results for the three validation pairs required by the exercise, plus commentary, are in
[`app/embedding_pipeline/SANITY_CHECK.md`](app/embedding_pipeline/SANITY_CHECK.md).

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
│   ├── routers/
│   │   ├── estimations.py           # /estimate and /estimate/stream (transactional)
│   │   └── sessions.py              # /sessions and /sessions/{id}/estimate (conversational)
│   ├── schemas/
│   │   ├── estimation.py            # Transactional request/response models and enums
│   │   └── sessions.py              # Session response models
│   ├── services/
│   │   ├── llm_router.py            # LiteLLM Router configuration and provider helpers
│   │   ├── llm_service.py           # generate_estimation, stream_estimation, generate_from_messages
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
│       ├── schemas.py               # Budget, Chunk, EmbeddedChunk, Ingest request/response models
│       ├── chunker.py                # JSONStructuralChunker — one budget component = one chunk
│       ├── embedder.py               # Embedder (OpenAI / Ollama), get_embedder() factory
│       ├── router.py                  # POST /embeddings/ingest
│       └── SANITY_CHECK.md           # Cosine similarity results for the 3 validation pairs
├── scripts/
│   └── compare.py                    # CLI: cosine similarity between two embedded texts
├── data/
│   └── budgets_sample.json           # 15 sample historical budgets used by embedding_pipeline
├── tests/
│   ├── cache/
│   │   └── test_exact_match.py      # Unit tests for ExactMatchCache
│   ├── prompts/
│   │   └── test_estimation_v1.py    # Unit tests for prompt templates
│   └── sessions/
│       └── test_sessions.py         # Integration tests for conversational flow
├── streamlit_app.py                 # Streamlit frontend (transactional + conversational modes)
└── pyproject.toml
```

## Security note

LiteLLM versions `1.82.7` and `1.82.8` are excluded in `pyproject.toml` due to a supply-chain compromise detected in March 2026. The constraint is `litellm>=1.34.0,!=1.82.7,!=1.82.8`.
