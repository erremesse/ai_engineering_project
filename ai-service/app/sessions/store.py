"""Almacén en memoria del proceso para las sesiones activas."""

import uuid

from app.sessions.models import Session


class SessionStore:
    """
    Registro en memoria de las sesiones activas.

    Sin persistencia deliberada: un diccionario en RAM es suficiente para esta
    fase. La volatilidad entre reinicios es un trade-off aceptado mientras no
    exista requisito de durabilidad.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        """Crea una sesión nueva, la registra y la devuelve."""
        session_id = str(uuid.uuid4())
        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        """Elimina una sesión. Devuelve True si existía."""
        return self._sessions.pop(session_id, None) is not None

    def __len__(self) -> int:
        return len(self._sessions)


session_store = SessionStore()
