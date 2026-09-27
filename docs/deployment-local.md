# Despliegue local con Docker Compose (Sesión 15)

Todo el estimador arranca con un único comando: cuatro contenedores en una red interna de compose.

```text
usuario ──► business-backend :3000   (Streamlit — único puerto publicado)
               ├──► postgres          (historial de estimaciones)
               └──► ai-service :8000  (FastAPI — solo red interna, exige X-Service-Token)
                       └──► vector-db (pgvector: documents / chunks)
```

| Servicio compose | Carpeta / imagen | Datastore | Puerto en el host |
| --- | --- | --- | --- |
| `business-backend` | `business-backend/` (Streamlit) | `postgres` | **3000** |
| `ai-service` | `ai-service/` (FastAPI + uv) | `vector-db` | — (ninguno) |
| `postgres` | `postgres:16` | volumen `business_postgres_data` | — |
| `vector-db` | `pgvector/pgvector:pg16` | volumen `postgres_data` | — |

## Arranque

Requisitos: Docker y Docker Compose (`docker --version`, `docker compose version`).

```bash
cp .env.example .env
# Rellena en .env: el proveedor LLM (ANTHROPIC_API_KEY / OPENAI_API_KEY / OLLAMA_API_BASE),
# AI_SERVICE_TOKEN (openssl rand -hex 32) y POSTGRES_PASSWORD. .env no se versiona.

docker compose build
docker compose up -d
```

- **Migraciones:** las aplica solas el entrypoint del servicio IA (`alembic upgrade head`).
- **Ingesta del corpus:** solo hace falta **la primera vez**, porque el resultado persiste en el volumen de `vector-db`. El proceso es idempotente: los documentos que ya existen responden 409 y se saltan.

```bash
docker compose exec ai-service python scripts/query_examples.py --corpus data/budgets_sample_es.json
```

## Las 5 comprobaciones

### 1. Los cuatro servicios están levantados y en estado healthy

```bash
docker compose ps
```

Tanto `ai-service` como `postgres` deben aparecer `(healthy)`, y también `vector-db` y `business-backend`, que tienen su propio healthcheck.

### 2. El frontend responde en http://localhost:3000

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/                 # 200
curl -s http://localhost:3000/_stcore/health                                    # ok
```

Abre http://localhost:3000 en el navegador.

### 3. El servicio IA no es accesible desde el host

```bash
curl -m 5 http://localhost:8000/health        # falla: connection refused, no hay puerto publicado
docker compose port ai-service 8000           # sin salida
```

Dentro de la red interna sí responde, y exige el token:

```bash
# /health está exento de token (lo usa el healthcheck)
docker compose exec business-backend python -c "import urllib.request as u; print(u.urlopen('http://ai-service:8000/health').read())"

# Sin X-Service-Token -> 401
docker compose exec business-backend python -c "import httpx; print(httpx.get('http://ai-service:8000/api/v1/cag/preview').status_code)"

# Con el token -> 200
docker compose exec business-backend python -c "import os, httpx; print(httpx.get('http://ai-service:8000/api/v1/cag/preview', headers={'X-Service-Token': os.environ['AI_SERVICE_TOKEN']}).status_code)"
```

### 4. Una estimación recorre el flujo completo

En http://localhost:3000:

1. Elige el modo **RAG (transcripción)**.
2. Pulsa **Cliente claro**.
3. Pulsa **Generar estimación**.

El flujo es business-backend → ai-service (con `X-Service-Token`) → vector-db (búsqueda pgvector) → LLM → respuesta con confianza, desglose y fuentes citadas. La estimación aparece además en **Historial**, en la barra lateral, porque se ha guardado en `postgres`.

Para verlo en los logs:

```bash
docker compose logs ai-service | grep -E "retrieval|generation|service_token"
docker compose exec postgres psql -U app -d estimation -c "select id, created_at, mode from estimations order by id desc limit 5;"
```

### 5. Reinicio completo sin pasos manuales

```bash
docker compose down        # sin -v: los volúmenes se conservan
docker compose up -d
docker compose ps          # vuelven a estar healthy
docker compose exec vector-db psql -U estimator -d estimator -c "select count(*) from chunks;"   # el corpus sigue ahí
docker compose exec postgres psql -U app -d estimation -c "select count(*) from estimations;"   # el historial sigue ahí
```

Tras el reinicio, una nueva estimación funciona sin tener que volver a migrar ni a ingerir.

`docker compose down -v` borra los volúmenes. Obliga a repetir la ingesta y, por tanto, a volver a pagar los embeddings.

## Autenticación entre servicios

- **`X-Service-Token`**, definido en `ai-service/app/api/service_token.py`, es un middleware que se aplica a **todas** las rutas del servicio IA.
  - Solo quedan exentos `/health`, `/docs` y `/openapi.json`.
  - Compara el valor con `AI_SERVICE_TOKEN` usando `secrets.compare_digest`.
  - En compose la variable es obligatoria: sin ella, `docker compose up` falla con un mensaje explícito.
- El cliente es `business-backend/ai_client.py` (`AiServiceClient`), que añade la cabecera a todas las peticiones.
- Como segunda capa se mantiene la `X-API-Key` de la Sesión 09 (`RETRIEVAL_API_KEY` / `ESTIMATE_API_KEY`) en las rutas RAG.

## Modo desarrollo

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Este modo publica el servicio IA en `:8000` (con `/docs` y `--reload`) y `vector-db` en `:5432`. **No sirve** para las comprobaciones de arriba, porque la número 3 falla a propósito.

## Protección de datos

El historial guarda las transcripciones tal y como se introducen. No incluyas datos personales identificables (RGPD / LOPDGDD). 

## Incidencias encontradas al desplegar

Ejecutar la estimación RAG de extremo a extremo dentro de los contenedores sacó a la luz tres fallos latentes de las Sesiones 09 y 10, que antes no se habían ejercitado. Ninguno tiene que ver con Docker.

| Síntoma | Causa | Arreglo |
| --- | --- | --- |
| `401 Invalid or missing API key` en `/v1/estimate/from-transcript` con `ESTIMATE_API_KEY=` vacío | pydantic lee `""`, no `None`, y `_check_key` solo desactivaba la comprobación con `None` | [`security.py`](../ai-service/app/api/security.py): `if not expected` |
| `502`: JSON inválido con Claude | Anthropic no admite `json_schema` estricto vía LiteLLM y envuelve el JSON en un bloque ```` ```json ```` | [`llm_service.py`](../ai-service/app/services/llm_service.py): `strip_code_fence()` antes de validar (con test) |
| `502`: JSON truncado (`finish_reason='length'`) | `MAX_TOKENS=1500` no bastaba para el `Estimate` estructurado. Además, **Claude Sonnet 5 usa *adaptive thinking* por defecto y esos tokens cuentan en `max_tokens`**, así que con 4096 seguía truncando | `MAX_TOKENS=16000`. Es un techo, no un objetivo: solo se facturan los tokens usados |

### Modelo del generador

Con `LLM_PROVIDER=ollama` (`llama3.3:70b`), las 3 transcripciones de ejemplo devuelven `confidence: insufficient`. Sin embargo, el retrieval funciona correctamente: el presupuesto de ecommerce equivalente aparece a una distancia coseno de 0,18. El modelo local es más conservador con el prompt de la Sesión 09.

Para la verificación se usa `LLM_PROVIDER=anthropic` con `ANTHROPIC_MODEL=claude-sonnet-5`. Los embeddings siguen en Ollama (`nomic-embed-text`, 768 dimensiones), así que el corpus ya ingerido sigue siendo válido. Si se cambiara `EMBEDDING_PROVIDER`, habría que volver a ingerirlo.

## Problemas conocidos

- **La primera compilación tarda.** La imagen del servicio IA incluye torch en su versión CPU, que ocupa alrededor de 1 GB, para el reranker de la Sesión 10.
- **El modelo del reranker se descarga en el primer uso** (`RAG_RERANK_ENABLED=true`) y se guarda en el volumen `hf_cache`.
- **Ollama local:** si `OLLAMA_API_BASE` apunta a un Ollama que corre en tu propia máquina, desde el contenedor hay que usar `http://host.docker.internal:11434` en lugar de `localhost`.
