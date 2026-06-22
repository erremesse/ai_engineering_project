"""Extracción heurística de metadata del proyecto a partir de los turnos."""

import re

from app.sessions.models import ProjectMetadata

_TECH_KEYWORDS: frozenset[str] = frozenset({
    "react", "vue", "angular", "next.js", "nextjs", "svelte",
    "python", "fastapi", "django", "flask", "node", "nodejs",
    "typescript", "javascript", "java", "kotlin", "swift",
    "postgresql", "mysql", "mongodb", "redis", "sqlite",
    "docker", "kubernetes", "aws", "azure", "gcp",
    "react native", "flutter", "ios", "android",
    "graphql", "rest", "grpc",
})

_TEAM_RE = re.compile(
    r"(\d+)\s*(?:desarrolladores?|ingenieros?|personas?|devs?|programadores?)",
    re.IGNORECASE,
)
_PROJECT_NAME_RE = re.compile(
    r"(?:proyecto|plataforma|aplicaci[oó]n|sistema|llamaremos|llamamos|se llama|denominamos)"
    r"\s+[«\"]?([A-Za-záéíóúÁÉÍÓÚñÑ][A-Za-záéíóúÁÉÍÓÚñÑ0-9 _\-]{1,40})[»\"]?",
    re.IGNORECASE,
)


class MetadataExtractor:
    """
    Actualiza ProjectMetadata con heurísticas sobre el texto del turno.

    Estrategia heurística (sin llamada extra al LLM): más barata y suficiente
    para esta fase. Un extractor LLM sería más robusto pero añadiría latencia
    y coste por turno.

    Reglas de actualización:
    - project_name: primera coincidencia en el transcript del usuario; inmutable
      una vez establecido.
    - assumed_team_size: primera mención numérica en cualquiera de los dos textos;
      inmutable una vez establecido.
    - mentioned_technologies: acumulativo entre turnos (unión de conjuntos).
    - agreed_scope: resumen del transcript del usuario en el primer turno;
      inmutable una vez establecido para no perder el contexto original.
    """

    def update(
        self,
        metadata: ProjectMetadata,
        user_text: str,
        assistant_text: str,
    ) -> ProjectMetadata:
        combined = f"{user_text}\n{assistant_text}".lower()

        # Tecnologías — acumulativo
        found_techs = {t for t in _TECH_KEYWORDS if t in combined}
        merged_techs = list(
            {t.lower() for t in metadata.mentioned_technologies} | found_techs
        )

        # Nombre del proyecto — sólo en el texto del usuario, sólo en primer hallazgo
        project_name = metadata.project_name
        if project_name is None:
            m = _PROJECT_NAME_RE.search(user_text)
            if m:
                project_name = m.group(1).strip()

        # Tamaño del equipo — primera mención numérica
        team_size = metadata.assumed_team_size
        if team_size is None:
            m = _TEAM_RE.search(combined)
            if m:
                team_size = int(m.group(1))

        # Alcance acordado — descripción del usuario en el primer turno; inmutable después
        agreed_scope = metadata.agreed_scope
        if agreed_scope is None and user_text:
            agreed_scope = user_text[:400]

        return ProjectMetadata(
            project_name=project_name,
            assumed_team_size=team_size,
            mentioned_technologies=merged_techs,
            agreed_scope=agreed_scope,
        )


metadata_extractor = MetadataExtractor()
