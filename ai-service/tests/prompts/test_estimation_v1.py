"""
Template rendering tests for estimation/v1.
No LLM calls — these run in milliseconds against the Jinja2 output only.
"""
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import EstimationRequest, ProjectType, DetailLevel, OutputFormat

_DESCRIPTION = (
    "Aplicacion web para gestion de proyectos con tablero kanban "
    "y sistema de reportes automaticos exportables a PDF."
)


def _req(**overrides) -> EstimationRequest:
    defaults = dict(
        description=_DESCRIPTION,
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
    )
    return EstimationRequest(**{**defaults, **overrides})


# --- Test 1: description block in user prompt ---

def test_description_wrapped_in_project_description_block():
    _, user = render_estimation_prompt(_req())
    assert "<project_description>" in user
    assert _DESCRIPTION in user
    assert "</project_description>" in user


# --- Test 2: output_format conditional ---

def test_phases_table_format_contains_column_header():
    system, _ = render_estimation_prompt(_req(output_format=OutputFormat.PHASES_TABLE))
    assert "| Fase | Descripción | Horas | Coste (EUR) |" in system


def test_narrative_format_does_not_contain_phases_table_column_header():
    system, _ = render_estimation_prompt(_req(output_format=OutputFormat.NARRATIVE))
    assert "| Fase | Descripción | Horas | Coste (EUR) |" not in system


# --- Test 3: detail_level conditional ---

def test_detailed_level_includes_exhaustive_instruction():
    system, _ = render_estimation_prompt(_req(detail_level=DetailLevel.DETAILED))
    assert "exhaustivo" in system.lower()


def test_summary_level_excludes_exhaustive_instruction():
    system, _ = render_estimation_prompt(_req(detail_level=DetailLevel.SUMMARY))
    assert "exhaustivo" not in system.lower()
