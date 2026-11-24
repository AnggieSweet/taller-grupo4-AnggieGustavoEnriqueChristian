# Imagen para Heroku (stack "container") u otra plataforma con Docker.
# Instala las dependencias de LangGraph y de CrewAI en un mismo entorno y
# levanta los seis agentes y la API en un solo proceso (scripts/servidor_unico.py).
FROM python:3.12-slim

ENV PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CREWAI_DISABLE_TELEMETRY=true \
    OTEL_SDK_DISABLED=true

WORKDIR /app

COPY requirements.txt requirements-crew.txt ./
RUN pip install -r requirements.txt -r requirements-crew.txt

COPY . .

RUN useradd --create-home agente && chown -R agente /app
USER agente

# Heroku entrega el puerto en $PORT; en local se usa 8010.
CMD ["python", "-m", "scripts.servidor_unico"]
