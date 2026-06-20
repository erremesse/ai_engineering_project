import json
from collections.abc import AsyncIterator
from app.services.llm_router import router, default_model_name, infer_provider

MAX_TOKENS = 1500


async def generate_estimation(system: str, user: str) -> dict:
    response = await router.acompletion(
        model="estimator",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=MAX_TOKENS,
    )
    model = response.model or default_model_name()
    return {
        "text": response.choices[0].message.content,
        "model": model,
        "provider": infer_provider(model),
        "usage": {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }


async def stream_estimation(system: str, user: str) -> AsyncIterator[str]:
    response = await router.acompletion(
        model="estimator",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=MAX_TOKENS,
        stream=True,
        stream_options={"include_usage": True},
    )

    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    model_used = default_model_name()

    async for chunk in response:
        if chunk.model:
            model_used = chunk.model
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        if getattr(chunk, "usage", None) is not None:
            usage = {
                "input_tokens": chunk.usage.prompt_tokens or 0,
                "output_tokens": chunk.usage.completion_tokens or 0,
                "total_tokens": chunk.usage.total_tokens or 0,
            }

    yield "\x00" + json.dumps({"model": model_used, **usage})
