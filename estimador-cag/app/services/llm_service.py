# from openai import OpenAI
import anthropic
import json
from collections.abc import AsyncIterator
from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES, format_examples

settings = get_settings()
# client = OpenAI(api_key=settings.OPENAI_API_KEY)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY) #Synchronous client
async_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) #Asynchronous client

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
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


async def stream_estimation(transcription: str) -> AsyncIterator[str]:
    async with async_client.messages.stream(
        model=settings.LLM_MODEL,
        system=build_system_prompt(),
        messages=[{"role": "user", "content": transcription}],
        max_tokens=1000,
    ) as stream:
        async for text in stream.text_stream:
            yield text
        final = await stream.get_final_message()
        yield "\x00" + json.dumps({
            "model": settings.LLM_MODEL,
            "input_tokens": final.usage.input_tokens,
            "output_tokens": final.usage.output_tokens,
        })