# Sanity check — embedding_pipeline

Validacion minima de que el pipeline de embeddings funciona end-to-end y discrimina
razonablemente entre textos semanticamente cercanos y lejanos.

> **Nota sobre el modelo usado:** el enunciado del ejercicio pide `text-embedding-3-small`
> de OpenAI. En este entorno no hay una API key de OpenAI real configurada, asi que la
> validacion se ha ejecutado con `EMBEDDING_PROVIDER=ollama` y el modelo local
> `nomic-embed-text:latest` servido por el Ollama remoto ya usado en el proyecto
> (`OLLAMA_API_BASE`). El pipeline es intercambiable entre backends (ver
> `app/embedding_pipeline/embedder.py`); en cuanto haya una API key de OpenAI real basta
> con cambiar `EMBEDDING_PROVIDER=openai` y repetir estos mismos comandos.

## Resultados

| Pareja | Texto 1 | Texto 2 | Similitud coseno | Expectativa |
| --- | --- | --- | --- | --- |
| A | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app | Authorization service using JSON Web Tokens for a banking application | **0.6979** | alta (> 0.6) |
| B | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app | Database migration from MySQL to PostgreSQL with zero downtime | **0.3916** | baja (< 0.4) |
| C | Backend services | API development | **0.5172** | sin expectativa fija |

Comandos ejecutados (dentro del entorno del proyecto, con `EMBEDDING_PROVIDER=ollama`):

```bash
uv run python scripts/compare.py --text-a "OAuth 2.0 authentication backend with JWT tokens for fintech mobile app" --text-b "Authorization service using JSON Web Tokens for a banking application"
uv run python scripts/compare.py --text-a "OAuth 2.0 authentication backend with JWT tokens for fintech mobile app" --text-b "Database migration from MySQL to PostgreSQL with zero downtime"
uv run python scripts/compare.py --text-a "Backend services" --text-b "API development"
```

## Comentario

Los resultados de las parejas A y B encajan con la intuicion: los dos textos sobre
autenticacion/autorizacion quedan claramente mas cerca entre si (0.70) que el par sin
relacion tematica (0.39), aunque el margen entre ambos es mas estrecho de lo que cabria
esperar con `text-embedding-3-small` — es coherente con que `nomic-embed-text` es un
modelo mas pequeno y con menor capacidad de discriminacion fina. La pareja C es la mas
interesante: dos frases genericas y de una sola linea ("Backend services" / "API
development") obtienen una similitud intermedia (0.52), ni claramente alta ni baja. Tiene
sentido: ambos textos comparten el dominio general de desarrollo de software pero no
describen el mismo componente concreto, asi que el modelo los coloca en una zona
ambigua — justo el tipo de caso donde la falta de contexto (sin el "contextual chunk
header" que si usamos en el chunker de presupuestos) hace mas dificil discriminar.
Seria buen material para repetir esta misma pareja con `text-embedding-3-small` en el
directo y comparar si un modelo mayor separa mejor estos casos genericos.
