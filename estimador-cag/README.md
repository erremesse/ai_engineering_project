# Estimador CAG

Software project estimation service powered by LLMs. A FastAPI backend generates structured effort estimations from project descriptions using CAG (Context-Augmented Generation) with few-shot examples. A Streamlit frontend provides a form-based interface with real-time streaming support.

## Stack

- **Python 3.11+** / **FastAPI** / **Uvicorn**
- **Streamlit** — web frontend with form input and streaming display
- **LiteLLM Router** — provider aggregator with automatic fallback chain
- **Pydantic v2 + Pydantic Settings** for schemas and configuration

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
| `NUM_CAG_EXAMPLES` | `5` | Default number of few-shot examples injected into the prompt |
| `APP_ENV` | `development` | Runtime environment |
| `LOG_LEVEL` | `DEBUG` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ESTIMADOR_API_URL` | `http://localhost:8000/api/v1/estimate` | API base URL consumed by Streamlit |

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

### `POST /api/v1/estimate`

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
  "prompt_version": "1.0",
  "model": "claude-haiku-4-5-20251001",
  "provider": "anthropic",
  "usage": {
    "input_tokens": 1842,
    "output_tokens": 512,
    "total_tokens": 2354
  }
}
```

### `POST /api/v1/estimate/stream`

Same request body as above. Returns a plain-text stream of tokens. The final chunk is prefixed with `\x00` and contains a JSON object with `model`, `input_tokens`, `output_tokens`, and `total_tokens`.

### `GET /health`

Returns `{"status": "healthy"}`.

## Project structure

```text
estimador-cag/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings (Pydantic Settings + .env)
│   ├── routers/
│   │   └── estimations.py       # /estimate and /estimate/stream routes
│   ├── schemas/
│   │   └── estimation.py        # Request/response Pydantic models and enums
│   ├── services/
│   │   ├── llm_router.py        # LiteLLM Router configuration and provider helpers
│   │   └── llm_service.py       # Prompt building, generate_estimation, stream_estimation
│   └── context/
│       └── examples.py          # Few-shot CAG examples
├── streamlit_app.py             # Streamlit frontend
└── pyproject.toml
```

## Security note

LiteLLM versions `1.82.7` and `1.82.8` are excluded in `pyproject.toml` due to a supply-chain compromise detected in March 2026. The constraint is `litellm>=1.34.0,!=1.82.7,!=1.82.8`.
