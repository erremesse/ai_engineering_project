import json
import time
from collections.abc import AsyncIterator

import structlog

from app.services.cache import cache
from app.services.llm_router import router, default_model_name, infer_provider

_MODEL_ALIAS = "estimator"
MAX_TOKENS = 1500

logger = structlog.get_logger()


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
