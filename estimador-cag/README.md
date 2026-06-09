# Estimador CAG

REST API that takes a software project transcription or description and returns a structured effort estimation, powered by Claude (Anthropic).

## Stack

- **Python 3.11+** / **FastAPI** / **Uvicorn**
- **Anthropic SDK** — Claude Haiku 4.5 by default
- **Pydantic Settings** for configuration

## Setup

```bash
# Install dependencies
uv pip install -e .

# Configure environment
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

## Environment variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `LLM_PROVIDER` | No | `anthropic` | `openai` or `anthropic` |
| `LLM_MODEL` | No | `claude-haiku-4-5` | Model identifier |
| `APP_ENV` | No | `development` | Runtime environment |
| `LOG_LEVEL` | No | `DEBUG` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Run

```bash
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Endpoints

### `POST /api/v1/estimate`

Generates an effort estimation from a project description.

#### Request

```json
{
  "transcription": "We need a mobile app with login, user profiles, and a dashboard... (min 50 chars)"
}
```

#### Response

```json
{
  "estimation": "...",
  "model": "claude-haiku-4-5",
  "provider": "anthropic"
}
```

### `GET /health`

Returns `{"status": "healthy"}`.

## Project structure

```text
app/
├── main.py              # FastAPI app
├── config.py            # Settings
├── routers/             # Route definitions
├── schemas/             # Pydantic models
├── services/            # LLM integration
└── context/             # Few-shot examples for prompting
```
