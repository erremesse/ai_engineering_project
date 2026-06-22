from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES, format_examples
from app.schemas.estimation import EstimationRequest, ProjectType
from app.sessions.models import ProjectMetadata

_PROMPTS_DIR = Path(__file__).parent
_settings = get_settings()

_PROJECT_TYPE_LABELS: dict[ProjectType, str] = {
    ProjectType.MOBILE_APP: "aplicación móvil (iOS y/o Android)",
    ProjectType.WEB_SAAS: "plataforma web o SaaS",
    ProjectType.INTERNAL_TOOL: "herramienta interna o backoffice",
    ProjectType.DATA_PIPELINE: "pipeline de datos o sistema de analítica",
}


def _build_env(version: str) -> Environment:
    template_dir = _PROMPTS_DIR / "estimation" / version
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _base_context(request: EstimationRequest) -> dict:
    n = min(request.n_examples or _settings.NUM_CAG_EXAMPLES, len(ESTIMATION_EXAMPLES))
    return {
        "description": request.description,
        "project_type": request.project_type.value,
        "project_type_label": _PROJECT_TYPE_LABELS[request.project_type],
        "detail_level": request.detail_level.value,
        "output_format": request.output_format.value,
        "cag_examples": format_examples(ESTIMATION_EXAMPLES[:n]),
    }


def render_estimation_prompt(
    request: EstimationRequest,
    version: str = "v1",
) -> tuple[str, str]:
    """Renderiza system y user prompts para el endpoint transaccional (sin sesión).

    Returns (system_prompt, user_prompt) ready to send to the LLM.
    """
    env = _build_env(version)
    context = {**_base_context(request), "project_metadata": None}
    system = env.get_template("system.j2").render(context)
    user = env.get_template("user.j2").render(context)
    return system, user


def render_session_prompt(
    request: EstimationRequest,
    metadata: ProjectMetadata,
    version: str = "v1",
) -> tuple[str, str]:
    """Renderiza system y user prompts para el endpoint conversacional (con sesión).

    Inyecta el project_metadata en el system prompt cuando no está vacío.
    Returns (system_prompt, user_prompt) ready to send to the LLM.
    """
    env = _build_env(version)
    context = {
        **_base_context(request),
        "project_metadata": None if metadata.is_empty() else metadata,
    }
    system = env.get_template("system.j2").render(context)
    user = env.get_template("user.j2").render(context)
    return system, user
