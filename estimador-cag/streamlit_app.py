import streamlit as st
import httpx
import json
import time
import os
from app.services.llm_service import build_system_prompt
from app.context.examples import ESTIMATION_EXAMPLES

API_URL = os.getenv("ESTIMADOR_API_URL", "http://localhost:8000/api/v1/estimate")
STREAM_URL = API_URL + "/stream"

st.title("Estimador de proyectos software")

# --- Session state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None

# --- Sidebar ---
with st.sidebar:
    st.header("Modo de respuesta")
    streaming_mode = st.toggle("Streaming (token a token)", value=True)

    st.divider()

    st.header("System prompt activo")
    st.text_area(
        label="",
        value=build_system_prompt(),
        height=220,
        disabled=True,
        key="system_prompt_display",
    )

    st.divider()

    st.header("Contexto CAG — ejemplos inyectados")
    for i, example in enumerate(ESTIMATION_EXAMPLES, 1):
        with st.expander(f"Ejemplo {i}"):
            st.markdown("**Resumen de reunión:**")
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

# --- Chat history ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Input ---
if prompt := st.chat_input("Pega aqui la transcripcion o descripcion del proyecto..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        t0 = time.perf_counter()

        if streaming_mode:
            metadata_sink: dict = {}

            def _stream_response(text: str, sink: dict):
                with httpx.stream("POST", STREAM_URL, json={"transcription": text}, timeout=60) as r:
                    r.raise_for_status()
                    for chunk in r.iter_text():
                        if chunk.startswith("\x00"):
                            sink.update(json.loads(chunk[1:]))
                        else:
                            yield chunk

            try:
                estimation = st.write_stream(_stream_response(prompt, metadata_sink))
                metadata_sink["elapsed"] = time.perf_counter() - t0
                st.session_state.last_metrics = metadata_sink
            except httpx.HTTPStatusError as e:
                detail = e.response.json().get("detail", str(e))
                estimation = f"Error del servidor: {detail}"
                st.error(estimation)
            except httpx.RequestError:
                estimation = f"No se pudo conectar con `{STREAM_URL}`. Esta el servidor en marcha?"
                st.error(estimation)

        else:
            try:
                response = httpx.post(API_URL, json={"transcription": prompt}, timeout=60)
                response.raise_for_status()
                data = response.json()
                estimation = data["estimation"]
                usage = data.get("usage", {})
                st.session_state.last_metrics = {
                    "model": data.get("model", "—"),
                    "input_tokens": usage.get("input_tokens", "—"),
                    "output_tokens": usage.get("output_tokens", "—"),
                    "total_tokens": usage.get("total_tokens", "—"),
                    "elapsed": time.perf_counter() - t0,
                }
                st.markdown(estimation)
            except httpx.HTTPStatusError as e:
                detail = e.response.json().get("detail", str(e))
                estimation = f"Error del servidor: {detail}"
                st.error(estimation)
            except httpx.RequestError:
                estimation = f"No se pudo conectar con `{API_URL}`. Esta el servidor en marcha?"
                st.error(estimation)

    st.session_state.messages.append({"role": "assistant", "content": estimation})
