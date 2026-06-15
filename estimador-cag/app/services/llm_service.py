import json
from collections.abc import AsyncIterator
from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES, format_examples
from app.services.llm_router import router, default_model_name, infer_provider

settings = get_settings()
MAX_TOKENS = 1500


def build_system_prompt() -> str:
    examples_text = format_examples(ESTIMATION_EXAMPLES)
    return f"""Eres un consultor senior de software con 15 años de experiencia en estimación
de proyectos. Tu trabajo es analizar transcripciones de reuniones con clientes
y generar estimaciones detalladas de desarrollo de software.

A continuación se incluyen estimaciones de proyectos anteriores de la empresa.
Úsalas como referencia para calibrar tus estimaciones: los precios por hora,
la granularidad del desglose de tareas y la estructura del presupuesto deben
ser consistentes con estos ejemplos.

{examples_text}

Tu estimación debe incluir:
1. Resumen del proyecto (2-3 frases)
2. Desglose de tareas con horas estimadas y coste
3. Equipo recomendado
4. Duración total estimada
5. Riesgos o supuestos clave

Usa EUR como moneda. Redondea las horas a múltiplos de 5."""


async def generate_estimation(transcription: str) -> dict:
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": transcription},
    ]
    response = await router.acompletion(
        model="estimator",
        messages=messages,
        max_tokens=MAX_TOKENS,
    )
    model = response.model or default_model_name()
    return {
        "estimation": response.choices[0].message.content,
        "model": model,
        "provider": infer_provider(model),
        "usage": {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }


async def stream_estimation(transcription: str) -> AsyncIterator[str]:
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": transcription},
    ]
    response = await router.acompletion(
        model="estimator",
        messages=messages,
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
