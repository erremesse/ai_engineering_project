import tiktoken

from app.embedding_pipeline.schemas import Budget, Chunk

# El conteo de tokens usa siempre el tokenizer de OpenAI como proxy de tamano,
# independientemente del EMBEDDING_PROVIDER configurado (tiktoken no soporta modelos Ollama).
_TOKENIZER_MODEL = "text-embedding-3-small"

_CHUNK_TEMPLATE = (
    "[Project: {project_summary}]\n"
    "[Client sector: {sector} | Year: {year} | Main tech: {main_technology}]\n\n"
    "Component: {component_name}\n"
    "Description: {component_description}\n"
    "Tech stack: {tech_stack}\n"
    "Complexity: {complexity}\n"
    "Estimated hours: {estimated_hours}"
)


class JSONStructuralChunker:
    """Chunker estructural para presupuestos JSON: un componente = un chunk."""

    def __init__(self) -> None:
        self._encoding = tiktoken.encoding_for_model(_TOKENIZER_MODEL)

    def chunk(self, budgets: list[Budget]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for budget in budgets:
            for component in budget.components:
                text = _CHUNK_TEMPLATE.format(
                    project_summary=budget.project_summary,
                    sector=budget.client_metadata.sector,
                    year=budget.year,
                    main_technology=budget.main_technology,
                    component_name=component.name,
                    component_description=component.description,
                    tech_stack=", ".join(component.tech_stack),
                    complexity=component.complexity,
                    estimated_hours=component.estimated_hours,
                )
                chunks.append(
                    Chunk(
                        chunk_id=f"{budget.budget_id}::{component.component_id}",
                        text=text,
                        metadata={
                            "budget_id": budget.budget_id,
                            "component_id": component.component_id,
                            "client_sector": budget.client_metadata.sector,
                            "main_technology": budget.main_technology,
                            "year": budget.year,
                            "complexity": component.complexity,
                            "estimated_hours": component.estimated_hours,
                        },
                        token_count=len(self._encoding.encode(text)),
                    )
                )
        return chunks
