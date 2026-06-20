import streamlit as st
import httpx
import json
import time
import os
from app.schemas.estimation import EstimationRequest, ProjectType, DetailLevel, OutputFormat
from app.prompts.loader import render_estimation_prompt
from app.context.examples import ESTIMATION_EXAMPLES

API_URL = os.getenv("ESTIMADOR_API_URL", "http://localhost:8000/api/v1/estimate")
STREAM_URL = API_URL + "/stream"

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

st.title("Estimador de proyectos software")

# --- Session state ---
if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_form_values" not in st.session_state:
    st.session_state.last_form_values = {
        "project_type": ProjectType.WEB_SAAS,
        "detail_level": DetailLevel.MEDIUM,
        "output_format": OutputFormat.PHASES_TABLE,
        "n_examples": len(ESTIMATION_EXAMPLES),
    }

# --- Sidebar ---
with st.sidebar:
    st.header("Modo de respuesta")
    streaming_mode = st.toggle("Streaming (token a token)", value=True)

    st.divider()

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

# --- Form ---
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
        index=list(ProjectType).index(st.session_state.last_form_values["project_type"]),
    )
    detail_level = col2.radio(
        "Nivel de detalle",
        options=list(DetailLevel),
        format_func=lambda x: _DETAIL_LEVEL_LABELS[x],
        index=list(DetailLevel).index(st.session_state.last_form_values["detail_level"]),
    )
    output_format = col3.radio(
        "Formato de salida",
        options=list(OutputFormat),
        format_func=lambda x: _OUTPUT_FORMAT_LABELS[x],
        index=list(OutputFormat).index(st.session_state.last_form_values["output_format"]),
    )

    submitted = st.form_submit_button("Estimar", type="primary", use_container_width=True)

# --- On submit ---
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
                with httpx.stream(
                    "POST",
                    STREAM_URL,
                    json=payload,
                    timeout=httpx.Timeout(connect=10, read=300, write=10, pool=5),
                ) as r:
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
                st.error(f"No se pudo conectar con `{STREAM_URL}`. Esta el servidor en marcha?")

        else:
            try:
                response = httpx.post(
                    API_URL,
                    json=payload,
                    timeout=httpx.Timeout(connect=10, read=300, write=10, pool=5),
                )
                response.raise_for_status()
                data = response.json()
                result_text = data["text"]
                usage = data.get("usage", {})
                st.session_state.last_metrics = {
                    "model": data.get("model", "—"),
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
                st.error(f"No se pudo conectar con `{API_URL}`. Esta el servidor en marcha?")

# --- Show previous result if no new submission ---
elif st.session_state.last_result and not submitted:
    st.markdown(st.session_state.last_result)
