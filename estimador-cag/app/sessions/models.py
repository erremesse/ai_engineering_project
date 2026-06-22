"""
Modelos de datos del estado conversacional.

Sin persistencia deliberada: un diccionario en RAM es suficiente para esta fase
porque el objetivo es explorar los patrones de memoria conversacional, no construir
un sistema de producción. La volatilidad entre reinicios es un trade-off aceptado.
"""

from collections import deque

from pydantic import BaseModel, Field

MAX_TURNS = 6


class ProjectMetadata(BaseModel):
    """Hechos conocidos del proyecto en curso, mantenidos entre turnos."""

    project_name: str | None = None
    assumed_team_size: int | None = None
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = None

    def is_empty(self) -> bool:
        return (
            self.project_name is None
            and self.assumed_team_size is None
            and not self.mentioned_technologies
            and self.agreed_scope is None
        )


class ConversationHistory:
    """
    Historial de mensajes con ventana deslizante.

    El system prompt se regenera en cada llamada a to_messages() para reflejar
    el project_metadata actualizado; no se almacena como entrada del historial.
    Los turnos más antiguos se descartan cuando se supera max_turns para
    mantener el contexto dentro del presupuesto de tokens.
    """

    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        self.max_turns = max_turns
        # Cada elemento es (user_content, assistant_content)
        self._turns: deque[tuple[str, str]] = deque()

    def add_turn(self, user_content: str, assistant_content: str) -> None:
        self._turns.append((user_content, assistant_content))
        while len(self._turns) > self.max_turns:
            self._turns.popleft()

    def turn_count(self) -> int:
        return len(self._turns)

    def to_messages(self, system: str) -> list[dict]:
        """Devuelve el array messages listo para pasar a la API del LLM."""
        messages: list[dict] = [{"role": "system", "content": system}]
        for user_content, assistant_content in self._turns:
            messages.append({"role": "user", "content": user_content})
            messages.append({"role": "assistant", "content": assistant_content})
        return messages


class Session:
    """Estado completo de una sesión conversacional."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.history = ConversationHistory()
        self.metadata = ProjectMetadata()
