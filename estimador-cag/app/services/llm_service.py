import json
from collections.abc import AsyncIterator
from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES, format_examples
from app.schemas.estimation import DetailLevel, OutputFormat, ProjectType
from app.services.llm_router import router, default_model_name, infer_provider

settings = get_settings()
MAX_TOKENS = 1500
PROMPT_VERSION = "1.0"

_PROJECT_CONTEXT: dict[ProjectType, str] = {
    ProjectType.MOBILE_APP: "aplicacion movil (iOS y/o Android)",
    ProjectType.WEB_SAAS: "plataforma web o SaaS",
    ProjectType.INTERNAL_TOOL: "herramienta interna o backoffice",
    ProjectType.DATA_PIPELINE: "pipeline de datos o sistema de analitica",
}

_DETAIL_INSTRUCTIONS: dict[DetailLevel, str] = {
    DetailLevel.SUMMARY: (
        "Genera un resumen ejecutivo breve: coste total estimado, equipo recomendado y duracion. "
        "Maximo 10 lineas."
    ),
    DetailLevel.MEDIUM: (
        "Genera un desglose por fases principales con horas estimadas y coste por fase. "
        "Incluye equipo y duracion total."
    ),
    DetailLevel.DETAILED: (
        "Genera un desglose completo de todas las tareas, con horas, coste, perfil necesario, "
        "riesgos clave y supuestos. Se exhaustivo."
    ),
}

_FORMAT_INSTRUCTIONS: dict[OutputFormat, str] = {
    OutputFormat.PHASES_TABLE: (
        "Presenta el resultado en una tabla Markdown con columnas: "
        "| Fase | Descripcion | Horas | Coste (EUR) |"
    ),
    OutputFormat.LINE_ITEMS: (
        "Presenta el resultado como una lista de partidas presupuestarias numeradas, "
        "con coste unitario y coste total por partida."
    ),
    OutputFormat.NARRATIVE: (
        "Presenta el resultado como un informe narrativo profesional, "
        "estructurado en secciones con titulos markdown."
    ),
}


def build_system_prompt(
    project_type: ProjectType,
    detail_level: DetailLevel,
    output_format: OutputFormat,
    n_examples: int | None = None,
) -> str:
    n = min(n_examples or settings.NUM_CAG_EXAMPLES, len(ESTIMATION_EXAMPLES))
    examples_text = format_examples(ESTIMATION_EXAMPLES[:n])
    return f"""Eres un consultor senior de software con 15 anos de experiencia en estimacion \
de proyectos. Analizas descripciones de proyectos de tipo {_PROJECT_CONTEXT[project_type]} \
y generas estimaciones detalladas de desarrollo de software.

A continuacion se incluyen estimaciones de proyectos anteriores de la empresa. \
Usalas como referencia para calibrar tus estimaciones: los precios por hora, \
la granularidad del desglose de tareas y la estructura del presupuesto deben \
ser consistentes con estos ejemplos.

{examples_text}

Instrucciones para esta estimacion:
- Nivel de detalle: {_DETAIL_INSTRUCTIONS[detail_level]}
- Formato de salida: {_FORMAT_INSTRUCTIONS[output_format]}
- Usa EUR como moneda y redondea las horas a multiples de 5."""


async def generate_estimation(
    description: str,
    project_type: ProjectType,
    detail_level: DetailLevel,
    output_format: OutputFormat,
    n_examples: int | None = None,
) -> dict:
    messages = [
        {"role": "system", "content": build_system_prompt(project_type, detail_level, output_format, n_examples)},
        {"role": "user", "content": description},
    ]
    response = await router.acompletion(
        model="estimator",
        messages=messages,
        max_tokens=MAX_TOKENS,
    )
    model = response.model or default_model_name()
    return {
        "text": response.choices[0].message.content,
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "provider": infer_provider(model),
        "usage": {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
    }


async def stream_estimation(
    description: str,
    project_type: ProjectType,
    detail_level: DetailLevel,
    output_format: OutputFormat,
    n_examples: int | None = None,
) -> AsyncIterator[str]:
    messages = [
        {"role": "system", "content": build_system_prompt(project_type, detail_level, output_format, n_examples)},
        {"role": "user", "content": description},
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
