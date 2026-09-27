import json
import re
import time
from collections.abc import AsyncIterator
from typing import TypeVar

import structlog
from pydantic import BaseModel

from app.observability import add_usage, add_usage_counts
from app.services.cache import cache
from app.services.llm_router import router, default_model_name, infer_provider

_MODEL_ALIAS = "estimator"
# Raised from 1500 (Sesion 15): the structured RAG Estimate JSON (breakdown + sources +
# assumptions + reasoning) was cut at finish_reason='length' with Claude and failed
# validation. Claude Sonnet 5 also runs adaptive thinking by default, and thinking
# tokens count against max_tokens (4096 was still not enough). ~16k is the recommended
# ceiling for non-streaming calls; it is a cap, not a target — only used tokens are
# billed. See docs/deployment-local.md, "Incidencias encontradas al desplegar".
MAX_TOKENS = 16000

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


async def generate_from_messages(messages: list[dict]) -> dict:
    """Llama al LLM con un array de mensajes completo (sesión conversacional).

    A diferencia de generate_estimation(), no usa caché: el historial varía en
    cada turno, por lo que la clave nunca coincidiría entre llamadas sucesivas
    de la misma sesión.

    Args:
        messages: Array listo para la API — [{"role": "system", ...},
                  {"role": "user", ...}, {"role": "assistant", ...}, ...]

    Returns:
        dict con claves: text, model, provider, usage.
    """
    t0 = time.perf_counter()
    logger.info("llm_call_started", conversational=True, turn_count=len(messages))
    try:
        response = await router.acompletion(
            model=_MODEL_ALIAS,
            messages=messages,
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "llm_call_failed",
            error_type=type(exc).__name__,
            error_msg=str(exc),
            latency_ms=latency_ms,
            conversational=True,
        )
        raise

    add_usage(response)
    model = response.model or default_model_name()
    provider = infer_provider(model)
    latency_ms = round((time.perf_counter() - t0) * 1000)
    logger.info(
        "llm_call_completed",
        model=model,
        provider=provider,
        tokens_in=response.usage.prompt_tokens,
        tokens_out=response.usage.completion_tokens,
        latency_ms=latency_ms,
        conversational=True,
    )
    return {
        "text": response.choices[0].message.content,
        "model": model,
        "provider": provider,
        "usage": {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }


async def generate_estimation(system: str, user: str) -> dict:
    cached = cache.get(system, user, _MODEL_ALIAS)
    if cached is not None:
        logger.info("llm_cache_hit", model=cached["model"], provider=cached["provider"])
        return cached

    t0 = time.perf_counter()
    logger.info("llm_call_started")
    try:
        response = await router.acompletion(
            model=_MODEL_ALIAS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "llm_call_failed",
            error_type=type(exc).__name__,
            error_msg=str(exc),
            latency_ms=latency_ms,
        )
        raise

    add_usage(response)
    model = response.model or default_model_name()
    provider = infer_provider(model)
    latency_ms = round((time.perf_counter() - t0) * 1000)
    logger.info(
        "llm_call_completed",
        model=model,
        provider=provider,
        tokens_in=response.usage.prompt_tokens,
        tokens_out=response.usage.completion_tokens,
        latency_ms=latency_ms,
        cache_hit=False,
        fallback_used=False,
    )
    result = {
        "text": response.choices[0].message.content,
        "model": model,
        "provider": provider,
        "usage": {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }
    cache.set(system, user, _MODEL_ALIAS, result)
    return result


async def stream_estimation(system: str, user: str) -> AsyncIterator[str]:
    cached = cache.get(system, user, _MODEL_ALIAS)
    if cached is not None:
        logger.info(
            "llm_cache_hit",
            model=cached["model"],
            provider=cached["provider"],
            streaming=True,
        )
        yield cached["text"]
        yield "\x00" + json.dumps({"model": cached["model"], **cached["usage"]})
        return

    t0 = time.perf_counter()
    logger.info("llm_call_started", streaming=True)
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    model_used = default_model_name()
    chunks: list[str] = []

    try:
        response = await router.acompletion(
            model=_MODEL_ALIAS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=MAX_TOKENS,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in response:
            if chunk.model:
                model_used = chunk.model
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                chunks.append(content)
                yield content
            if getattr(chunk, "usage", None) is not None:
                usage = {
                    "input_tokens": chunk.usage.prompt_tokens or 0,
                    "output_tokens": chunk.usage.completion_tokens or 0,
                    "total_tokens": chunk.usage.total_tokens or 0,
                }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "llm_call_failed",
            error_type=type(exc).__name__,
            error_msg=str(exc),
            latency_ms=latency_ms,
            streaming=True,
        )
        raise

    add_usage_counts(usage["input_tokens"], usage["output_tokens"], model_used)
    provider = infer_provider(model_used)
    latency_ms = round((time.perf_counter() - t0) * 1000)
    logger.info(
        "llm_call_completed",
        model=model_used,
        provider=provider,
        tokens_in=usage["input_tokens"],
        tokens_out=usage["output_tokens"],
        latency_ms=latency_ms,
        cache_hit=False,
        fallback_used=False,
        streaming=True,
    )
    cache.set(system, user, _MODEL_ALIAS, {
        "text": "".join(chunks),
        "model": model_used,
        "provider": provider,
        "usage": usage,
    })
    yield "\x00" + json.dumps({"model": model_used, **usage})


_CODE_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*\n(.*?)\n?\s*```\s*$", re.DOTALL)


def strip_code_fence(text: str) -> str:
    """Devuelve el contenido de un bloque ```json ... ``` si la respuesta viene envuelta.

    Anthropic (Claude) no soporta json_schema estricto via litellm y suele envolver el
    JSON en un bloque de codigo aunque el prompt pida JSON puro; sin esto la validacion
    falla en todos los intentos (visto en la Sesion 15 al pasar de Ollama a Anthropic).
    """
    match = _CODE_FENCE.match(text)
    return match.group(1) if match else text


async def generate_structured(system: str, user: str, schema: type[T], *, retries: int = 1) -> T:
    """Llama al LLM pidiendo un output que valide contra `schema` (Pydantic).

    El primer intento usa `response_format=schema` (litellm lo traduce a json_schema
    estricto para los proveedores que lo soportan). Si la validación falla — porque el
    proveedor activo no soporta json_schema estricto y `litellm.drop_params=True` lo
    descartó en silencio, o porque el modelo se desvió del esquema — se reintenta hasta
    `retries` veces sin `response_format`, reforzando en el propio prompt que la
    respuesta debe ser JSON puro conforme al esquema. Si se agotan los reintentos, se
    propaga la última excepción de validación/llamada.
    """
    t0 = time.perf_counter()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_exc: Exception | None = None

    for attempt in range(retries + 1):
        request_kwargs: dict = {"max_tokens": MAX_TOKENS}
        if attempt == 0:
            request_kwargs["response_format"] = schema
        else:
            messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "Tu respuesta anterior no era JSON valido para el esquema pedido.\n"
                        "Responde UNICAMENTE con un JSON valido que cumpla este esquema, "
                        "sin texto adicional ni bloques de codigo:\n"
                        f"{json.dumps(schema.model_json_schema())}"
                    ),
                }
            ]

        try:
            response = await router.acompletion(model=_MODEL_ALIAS, messages=messages, **request_kwargs)
            # Before validation: a failed attempt is billed as well.
            add_usage(response)
            result = schema.model_validate_json(strip_code_fence(response.choices[0].message.content))
            latency_ms = round((time.perf_counter() - t0) * 1000)
            logger.info(
                "structured_call_completed",
                schema=schema.__name__,
                attempt=attempt,
                latency_ms=latency_ms,
            )
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "structured_call_attempt_failed",
                schema=schema.__name__,
                attempt=attempt,
                error_type=type(exc).__name__,
                error_msg=str(exc),
            )

    latency_ms = round((time.perf_counter() - t0) * 1000)
    logger.error(
        "structured_call_failed",
        schema=schema.__name__,
        attempts=retries + 1,
        latency_ms=latency_ms,
        error_type=type(last_exc).__name__,
        error_msg=str(last_exc),
    )
    raise last_exc
