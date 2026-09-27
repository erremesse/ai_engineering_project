# Backend de negocio (Streamlit) — Sesion 15.
# Same pattern as the Rails reference: install deps, copy code, expose the port,
# start the server. Self-contained: it does NOT include the AI service code.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:3000/_stcore/health')"]

# browser.serverAddress: without it Streamlit looks up and logs the host's
# public IP ("External URL"), which should not end up in logs.
CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=3000", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false", \
     "--browser.serverAddress=localhost"]
