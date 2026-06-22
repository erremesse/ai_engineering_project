import json
import os
import time

import httpx
import streamlit as st

from app.context.examples import ESTIMATION_EXAMPLES
from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import DetailLevel, EstimationRequest, OutputFormat, ProjectType

# --- URL configuration ---
# ESTIMADOR_API_BASE: base URL of the FastAPI server (no trailing slash)
_API_BASE = os.getenv("ESTIMADOR_API_BASE", "http://localhost:8000")
_ESTIMATE_URL = f"{_API_BASE}/api/v1/estimate"
_STREAM_URL = f"{_API_BASE}/api/v1/estimate/stream"
_SESSIONS_URL = f"{_API_BASE}/api/v1/sessions"

_TIMEOUT = httpx.Timeout(connect=10, read=300, write=10, pool=5)

# --- Labels ---
_PROJECT_TYPE_LABELS: dict[ProjectType, str] = {
    ProjectType.MOBILE_APP: "Aplicacion movil",
    ProjectType.WEB_SAAS: "Web / SaaS",
    ProjectType.INTERNAL_TOOL: "Herramienta interna",
    ProjectType.DATA_PIPELINE: "Pipeline de datos",
}
_DETAIL_LEVEL_LABELS: dict[DetailLevel, str] = {
    DetailLevel.SUMMARY: "Resumen ejecutivo",
    DetailLevel.MEDIUM: "Desglose por fases",
    DetailLevel.DETAILED: "Desglose completo",
}
_OUTPUT_FORMAT_LABELS: dict[OutputFormat, str] = {
    OutputFormat.PHASES_TABLE: "Tabla de fases",
    OutputFormat.LINE_ITEMS: "Partidas de presupuesto",
    OutputFormat.NARRATIVE: "Informe narrativo",
}

_DEFAULT_FORM_VALUES = {
    "project_type": ProjectType.WEB_SAAS,
    "detail_level": DetailLevel.MEDIUM,
    "output_format": OutputFormat.PHASES_TABLE,
    "n_examples": len(ESTIMATION_EXAMPLES),
}


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _create_session() -> str | None:
    try:
        r = httpx.post(_SESSIONS_URL, timeout=10)
        r.raise_for_status()
        return r.json()["session_id"]
    except Exception as exc:
        st.error(f"No se pudo crear la sesion con el servidor: {exc}")
        return None


def _reset_session_state():
    st.session_state.session_id = _create_session()
    st.session_state.chat_history = []
    st.session_state.last_metadata = None
    st.session_state.last_metrics = None
    st.session_state.last_result = None
    st.session_state.last_form_values = _DEFAULT_FORM_VALUES.copy()


# ---------------------------------------------------------------------------
# State initialization (runs once per browser session)
# ---------------------------------------------------------------------------

if "session_id" not in st.session_state:
    _reset_session_state()

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

st.title("Estimador de proyectos software")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    mode = st.radio("Modo de uso", ["Conversacional", "Transaccional"], horizontal=True)

    st.divider()

    # --- Conversational controls ---
    if mode == "Conversacional":
        st.header("Sesion activa")
        sid = st.session_state.session_id
        if sid:
            st.caption(f"ID: `{sid[:8]}...`")
            turns = sum(1 for m in st.session_state.chat_history if m["role"] == "user")
            st.caption(f"Turnos: {turns}")
        else:
            st.warning("Sin sesion activa.")

        if st.button("Nueva conversacion", type="secondary", use_container_width=True):
            _reset_session_state()
            st.rerun()

        st.divider()

        st.header("Contexto del proyecto")
        metadata = st.session_state.last_metadata
        if metadata:
            if metadata.get("project_name"):
                st.write(f"**Nombre:** {metadata['project_name']}")
            if metadata.get("assumed_team_size"):
                st.write(f"**Equipo:** {metadata['assumed_team_size']} personas")
            techs = metadata.get("mentioned_technologies", [])
            if techs:
                st.write(f"**Tecnologias:** {', '.join(techs)}")
            if metadata.get("agreed_scope"):
                with st.expander("Alcance acordado"):
                    st.caption(metadata["agreed_scope"])
        else:
            st.caption("Sin contexto todavia.")

        st.divider()

    # --- Transactional controls ---
    if mode == "Transaccional":
        st.header("Modo de respuesta")
        streaming_mode = st.toggle("Streaming (token a token)", value=True)
        st.divider()
    else:
        streaming_mode = False

    # --- Shared controls ---
    st.header("Ejemplos CAG en el prompt")
    n_examples = st.slider(
        label="",
        min_value=1,
        max_value=len(ESTIMATION_EXAMPLES),
        value=st.session_state.last_form_values["n_examples"],
        key="n_examples_slider",
    )

    st.divider()

    fv = st.session_state.last_form_values
    st.header("System prompt activo")
    _preview_request = EstimationRequest(
        description="Esta es una descripcion de prueba para la vista previa del prompt.",
        project_type=fv["project_type"],
        detail_level=fv["detail_level"],
        output_format=fv["output_format"],
    )
    _system_preview, _ = render_estimation_prompt(_preview_request)
    st.text_area(
        label="",
        value=_system_preview,
        height=220,
        disabled=True,
        key="system_prompt_display",
    )

    st.divider()

    st.header("Contexto CAG — ejemplos inyectados")
    for i, example in enumerate(ESTIMATION_EXAMPLES[:n_examples], 1):
        with st.expander(f"Ejemplo {i}"):
            st.markdown("**Resumen de reunion:**")
            st.caption(example["meeting_summary"])
            st.markdown("**Estimacion de referencia:**")
            st.caption(example["estimation"])

    st.divider()

    st.header("Metricas — ultima llamada")
    if st.session_state.last_metrics:
        m = st.session_state.last_metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Tokens entrada", m.get("input_tokens", "—"))
        col2.metric("Tokens salida", m.get("output_tokens", "—"))
        col3.metric("Tokens total", m.get("total_tokens", "—"))
        st.metric("Tiempo de respuesta", f"{m.get('elapsed', 0):.2f} s")
        st.caption(f"Modelo: {m.get('model', '—')}")
    else:
        st.info("Aun no se ha realizado ninguna llamada.")


# ---------------------------------------------------------------------------
# Conversacional mode
# ---------------------------------------------------------------------------

if mode == "Conversacional":
    if not st.session_state.session_id:
        st.error("No hay sesion activa. Comprueba que el servidor esta en marcha y recarga la pagina.")
        st.stop()

    # Render chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    with st.form("conversational_form", clear_on_submit=True):
        transcript = st.text_area(
            "Transcripcion o descripcion del proyecto",
            placeholder="Describe el proyecto, refina el alcance o añade nueva informacion...",
            height=140,
        )
        uploaded_files = st.file_uploader(
            "Adjuntos opcionales (PDF, DOCX)",
            type=["pdf", "docx"],
            accept_multiple_files=True,
        )
        col1, col2, col3 = st.columns(3)
        project_type = col1.selectbox(
            "Tipo de proyecto",
            options=list(ProjectType),
            format_func=lambda x: _PROJECT_TYPE_LABELS[x],
            index=list(ProjectType).index(fv["project_type"]),
        )
        detail_level = col2.radio(
            "Nivel de detalle",
            options=list(DetailLevel),
            format_func=lambda x: _DETAIL_LEVEL_LABELS[x],
            index=list(DetailLevel).index(fv["detail_level"]),
        )
        output_format = col3.radio(
            "Formato de salida",
            options=list(OutputFormat),
            format_func=lambda x: _OUTPUT_FORMAT_LABELS[x],
            index=list(OutputFormat).index(fv["output_format"]),
        )
        submitted = st.form_submit_button("Enviar turno", type="primary", use_container_width=True)

    if submitted:
        if len(transcript.strip()) < 20:
            st.error("La transcripcion debe tener al menos 20 caracteres.")
        else:
            st.session_state.last_form_values = {
                "project_type": project_type,
                "detail_level": detail_level,
                "output_format": output_format,
                "n_examples": n_examples,
            }

            session_url = f"{_SESSIONS_URL}/{st.session_state.session_id}/estimate"
            form_data = {
                "transcript": transcript,
                "project_type": project_type.value,
                "detail_level": detail_level.value,
                "output_format": output_format.value,
                "n_examples": str(n_examples),
            }
            files_payload = [
                ("attachments", (f.name, f.getvalue(), f.type))
                for f in (uploaded_files or [])
            ]

            t0 = time.perf_counter()
            try:
                request_kwargs: dict = {"data": form_data, "timeout": _TIMEOUT}
                if files_payload:
                    request_kwargs["files"] = files_payload
                response = httpx.post(session_url, **request_kwargs)
                response.raise_for_status()
                resp_data = response.json()

                usage = resp_data.get("usage", {})
                st.session_state.last_metrics = {
                    "model": resp_data.get("model", "—"),
                    "input_tokens": usage.get("input_tokens", "—"),
                    "output_tokens": usage.get("output_tokens", "—"),
                    "total_tokens": usage.get("total_tokens", "—"),
                    "elapsed": time.perf_counter() - t0,
                }
                st.session_state.last_metadata = resp_data.get("metadata")

                user_label = transcript
                if files_payload:
                    filenames = ", ".join(f.name for f in (uploaded_files or []))
                    user_label += f"\n\n*Adjuntos: {filenames}*"
                st.session_state.chat_history.append({"role": "user", "content": user_label})
                st.session_state.chat_history.append({"role": "assistant", "content": resp_data["text"]})

                st.rerun()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    st.warning("La sesion ha expirado (reinicio del servidor). Creando nueva sesion...")
                    st.session_state.session_id = _create_session()
                    st.session_state.chat_history = []
                else:
                    detail = e.response.json().get("detail", str(e))
                    st.error(f"Error del servidor: {detail}")
            except httpx.RequestError:
                st.error(f"No se pudo conectar con `{session_url}`. Esta el servidor en marcha?")


# ---------------------------------------------------------------------------
# Transaccional mode
# ---------------------------------------------------------------------------

elif mode == "Transaccional":
    with st.form("estimation_form"):
        description = st.text_area(
            "Descripcion del proyecto",
            placeholder="Describe el proyecto de software a estimar (minimo 20 caracteres)...",
            height=160,
        )
        col1, col2, col3 = st.columns(3)
        project_type = col1.selectbox(
            "Tipo de proyecto",
            options=list(ProjectType),
            format_func=lambda x: _PROJECT_TYPE_LABELS[x],
            index=list(ProjectType).index(fv["project_type"]),
        )
        detail_level = col2.radio(
            "Nivel de detalle",
            options=list(DetailLevel),
            format_func=lambda x: _DETAIL_LEVEL_LABELS[x],
            index=list(DetailLevel).index(fv["detail_level"]),
        )
        output_format = col3.radio(
            "Formato de salida",
            options=list(OutputFormat),
            format_func=lambda x: _OUTPUT_FORMAT_LABELS[x],
            index=list(OutputFormat).index(fv["output_format"]),
        )
        submitted = st.form_submit_button("Estimar", type="primary", use_container_width=True)

    if submitted:
        if len(description.strip()) < 20:
            st.error("La descripcion debe tener al menos 20 caracteres.")
        else:
            st.session_state.last_form_values = {
                "project_type": project_type,
                "detail_level": detail_level,
                "output_format": output_format,
                "n_examples": n_examples,
            }
            payload = {
                "description": description,
                "project_type": project_type.value,
                "detail_level": detail_level.value,
                "output_format": output_format.value,
                "n_examples": n_examples,
            }
            t0 = time.perf_counter()

            if streaming_mode:
                metadata_sink: dict = {}

                def _stream_response(sink: dict):
                    with httpx.stream("POST", _STREAM_URL, json=payload, timeout=_TIMEOUT) as r:
                        r.raise_for_status()
                        for chunk in r.iter_text():
                            if chunk.startswith("\x00"):
                                sink.update(json.loads(chunk[1:]))
                            else:
                                yield chunk

                try:
                    result_text = st.write_stream(_stream_response(metadata_sink))
                    metadata_sink["elapsed"] = time.perf_counter() - t0
                    st.session_state.last_metrics = metadata_sink
                    st.session_state.last_result = result_text
                except httpx.HTTPStatusError as e:
                    st.error(f"Error del servidor: {e.response.json().get('detail', str(e))}")
                except httpx.RequestError:
                    st.error(f"No se pudo conectar con `{_STREAM_URL}`. Esta el servidor en marcha?")

            else:
                try:
                    response = httpx.post(_ESTIMATE_URL, json=payload, timeout=_TIMEOUT)
                    response.raise_for_status()
                    resp_data = response.json()
                    result_text = resp_data["text"]
                    usage = resp_data.get("usage", {})
                    st.session_state.last_metrics = {
                        "model": resp_data.get("model", "—"),
                        "input_tokens": usage.get("input_tokens", "—"),
                        "output_tokens": usage.get("output_tokens", "—"),
                        "total_tokens": usage.get("total_tokens", "—"),
                        "elapsed": time.perf_counter() - t0,
                    }
                    st.session_state.last_result = result_text
                    st.markdown(result_text)
                except httpx.HTTPStatusError as e:
                    st.error(f"Error del servidor: {e.response.json().get('detail', str(e))}")
                except httpx.RequestError:
                    st.error(f"No se pudo conectar con `{_ESTIMATE_URL}`. Esta el servidor en marcha?")

    elif st.session_state.last_result:
        st.markdown(st.session_state.last_result)
