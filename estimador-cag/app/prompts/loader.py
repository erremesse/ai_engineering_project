from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES, format_examples
from app.schemas.estimation import EstimationRequest, ProjectType

_PROMPTS_DIR = Path(__file__).parent
_settings = get_settings()

_PROJECT_TYPE_LABELS: dict[ProjectType, str] = {
    ProjectType.MOBILE_APP: "aplicación móvil (iOS y/o Android)",
    ProjectType.WEB_SAAS: "plataforma web o SaaS",
    ProjectType.INTERNAL_TOOL: "herramienta interna o backoffice",
    ProjectType.DATA_PIPELINE: "pipeline de datos o sistema de analítica",
}


def render_estimation_prompt(
    request: EstimationRequest,
    version: str = "v1",
) -> tuple[str, str]:
    """Render system and user prompts for an estimation request.

    Returns (system_prompt, user_prompt) ready to send to the LLM.
    """
    template_dir = _PROMPTS_DIR / "estimation" / version
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    n = min(request.n_examples or _settings.NUM_CAG_EXAMPLES, len(ESTIMATION_EXAMPLES))
    context = {
        "description": request.description,
        "project_type": request.project_type.value,
        "project_type_label": _PROJECT_TYPE_LABELS[request.project_type],
        "detail_level": request.detail_level.value,
        "output_format": request.output_format.value,
        "cag_examples": format_examples(ESTIMATION_EXAMPLES[:n]),
    }
    system = env.get_template("system.j2").render(context)
    user = env.get_template("user.j2").render(context)
    return system, user
