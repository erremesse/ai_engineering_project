# from openai import OpenAI
import anthropic
from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES, format_examples

settings = get_settings()
# client = OpenAI(api_key=settings.OPENAI_API_KEY)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

def build_system_prompt() -> str:
    examples_text = format_examples(ESTIMATION_EXAMPLES)
    return f"""Eres un experto en estimación de proyectos de software.
    
Utiliza los siguientes presupuestos históricos como referencia:

{examples_text}

Genera una estimación detallada para el proyecto descrito."""

async def generate_estimation(transcription: str) -> dict:
    system_prompt = build_system_prompt()
    
    # response = client.chat.completions.create(
    #     model=settings.LLM_MODEL,
    #     messages=[
    #         {"role": "system", "content": system_prompt},
    #         {"role": "user", "content": transcription}
    #     ]
    # )
    response = client.messages.create(
        model=settings.LLM_MODEL,
        system=system_prompt,
        messages=[
            {"role": "user", "content": transcription}
        ],
        max_tokens=1000
    )

    return {
        "estimation": response.content[0].text,
        "model": settings.LLM_MODEL,
        "provider": settings.LLM_PROVIDER,
    }