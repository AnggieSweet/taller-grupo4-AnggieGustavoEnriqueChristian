"""Construcción de la aplicación HTTP compartida por los agentes A2A."""

from fastapi import FastAPI

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard

from src.comun.executor import Executor


def crear_app(tarjeta: AgentCard, responder) -> FastAPI:
    """Crea FastAPI con el endpoint A2A, la ficha pública y salud."""
    app = FastAPI(title=tarjeta.name)
    executor = Executor(responder)
    manejador = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=tarjeta,
    )

    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(tarjeta),
        jsonrpc_routes=create_jsonrpc_routes(manejador, rpc_url="/"),
    )

    @app.get("/salud")
    async def salud() -> dict[str, bool]:
        return {"ok": True}

    return app
