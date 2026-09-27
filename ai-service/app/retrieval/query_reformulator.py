"""Reformulacion de transcripciones: extraccion estructurada con fallback a rewrite.

Extraccion estructurada (no HyDE, no query rewriting puro) porque produce un
artefacto inspeccionable (el JSON intermedio) y alimenta directamente los filtros
de metadata del retriever, no solo el texto que se embebe. Ver `EstimationQuery`.
"""

import structlog

from app.retrieval.schemas import EstimationQuery
from app.services.llm_service import generate_from_messages, generate_structured

logger = structlog.get_logger()

REFORMULATION_SYSTEM_PROMPT = """Eres un analista que extrae requisitos estructurados de \
transcripciones de reuniones comerciales sobre proyectos de software.

Extrae SOLO lo que este explicitamente mencionado o sea inequivocamente inferible del \
texto. No completes campos opcionales con sentido comun: si el cliente no menciona un \
sector, una regulacion o una tecnologia, deja ese campo vacio (null o lista vacia). No \
infieras GDPR solo porque hay datos personales, ni una tecnologia solo porque es habitual \
en ese tipo de proyecto.

Si se menciona un sector, prefiere uno de estos valores cuando encaje: finance, \
ecommerce, healthcare, industrial. Si no encaja ninguno, usa el termino tal cual lo dijo \
el cliente."""

_REWRITE_SYSTEM_PROMPT = """Reescribe la transcripcion de reunion que te pasan como una \
unica frase corta (una sola oracion) que describa la funcion principal del proyecto de \
software solicitado, en ingles, apta para busqueda semantica. No anadas informacion que \
no este en el texto."""


async def reformulate(transcript: str) -> EstimationQuery:
    """Extrae una `EstimationQuery` de la transcripcion; si la extraccion estructurada
    falla (proveedor sin soporte de json_schema estricto, o transcripcion ambigua),
    cae a un rewrite libre mas simple pero mejor que pasar la transcripcion cruda."""
    try:
        return await generate_structured(REFORMULATION_SYSTEM_PROMPT, transcript, EstimationQuery)
    except Exception as exc:
        logger.warning(
            "reformulation_fallback",
            error_type=type(exc).__name__,
            error_msg=str(exc),
        )
        rewritten = await generate_from_messages(
            [
                {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ]
        )
        return EstimationQuery(function=rewritten["text"].strip())


def compose_search_text(query: EstimationQuery) -> str:
    """Compone el texto sintetico que efectivamente se embebe para la busqueda."""
    parts = [query.function]
    if query.technologies:
        parts.append(f"with {', '.join(query.technologies)}")
    if query.sector:
        parts.append(f"for the {query.sector} sector")
    if query.country:
        parts.append(f"in {query.country}")
    if query.regulations:
        parts.append(f"compliant with {', '.join(query.regulations)}")
    if query.constraints:
        parts.append(f"requiring {', '.join(query.constraints)}")
    return ". ".join(parts) + "."
