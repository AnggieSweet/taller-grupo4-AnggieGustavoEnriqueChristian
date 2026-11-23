"""Construcción de la aplicación HTTP compartida por los agentes A2A."""

import logging
import os
from hmac import compare_digest

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard

from src.comun.executor import Executor

_registro = logging.getLogger("a2a.acceso")


def clave_agentes() -> str:
    """Clave compartida que protege el endpoint A2A (POST /) de los agentes. Vacía = sin protección."""
    return os.getenv("AGENT_API_KEY", "").strip()


def _clave_recibida(request: Request) -> str:
    """Lee la clave desde X-API-Key o desde Authorization: Bearer <clave>."""
    clave = request.headers.get("x-api-key", "").strip()
    if clave:
        return clave
    autorizacion = request.headers.get("authorization", "").strip()
    if autorizacion.lower().startswith("bearer "):
        return autorizacion[7:].strip()
    return ""


def crear_app(tarjeta: AgentCard, responder) -> FastAPI:
    """Crea FastAPI con el endpoint A2A, la ficha pública y salud.

    Si AGENT_API_KEY está definida, toda petición POST (endpoint JSON-RPC A2A) exige esa clave en
    X-API-Key o Authorization: Bearer. La ficha (GET /.well-known/agent-card.json) y GET /salud
    siguen siendo públicas para que el coordinador pueda descubrir al agente.
    """
    app = FastAPI(title=tarjeta.name)
    executor = Executor(responder)
    manejador = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=tarjeta,
    )

    if not clave_agentes():
        _registro.warning(
            "%s: AGENT_API_KEY no está definida; el endpoint A2A queda SIN protección "
            "(aceptable solo en local, nunca al exponerlo por túnel o en la nube).",
            tarjeta.name,
        )

    @app.middleware("http")
    async def exigir_clave_a2a(request: Request, call_next):
        esperada = clave_agentes()
        if esperada and request.method == "POST":
            recibida = _clave_recibida(request)
            if not recibida or not compare_digest(recibida, esperada):
                motivo = "sin_clave" if not recibida else "clave_invalida"
                _registro.warning("%s: acceso A2A rechazado (401) · motivo=%s", tarjeta.name, motivo)
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Acceso no autorizado al agente A2A."},
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)

    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(tarjeta),
        jsonrpc_routes=create_jsonrpc_routes(manejador, rpc_url="/"),
    )

    @app.get("/salud")
    async def salud() -> dict[str, bool]:
        return {"ok": True}

    return app
