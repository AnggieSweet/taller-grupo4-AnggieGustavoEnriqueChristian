"""Levanta los seis agentes y la API en un solo proceso.

Pensado para Heroku u otra plataforma que entrega un único puerto público
(variable PORT): los agentes escuchan solo dentro del contenedor, en 127.0.0.1
con sus puertos de siempre, y hablan entre sí por A2A igual que en local. La
API escucha en 0.0.0.0:$PORT y es lo único expuesto a internet.

Uso:  python -m scripts.servidor_unico
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import logging
import os
import sys

import uvicorn


# (nombre, módulo, puerto interno, variable con su URL)
AGENTES = [
    ("viajes", "src.agente_viajes.server", 8000, "URL_VIAJES"),
    ("restaurantes", "src.agente_restaurantes.server", 8001, "URL_RESTAURANTES"),
    ("anggie", "src.agente_anggie.server", 8003, "URL_ANGGIE"),
    ("enrique", "src.agente_enrique.server", 8004, "URL_ENRIQUE"),
    ("algomarket", "src.agente_algomarket.server", 8005, "URL_ALGOMARKET"),
    ("christian", "src.agente_christian.server", 8006, "URL_CHRISTIAN"),
]
AGENTES_DEL_GRUPO = ("URL_ANGGIE", "URL_ENRIQUE", "URL_ALGOMARKET", "URL_CHRISTIAN")
TIMEOUT_ARRANQUE = 90.0

_registro = logging.getLogger("servidor_unico")


class _ServidorInterno(uvicorn.Server):
    """Servidor de un agente: no captura señales; las maneja el de la API."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield


def _configurar_entorno() -> None:
    """Fija las URL internas antes de importar los agentes (las leen al importarse)."""
    for _, _, puerto, variable in AGENTES:
        os.environ.setdefault(variable, f"http://127.0.0.1:{puerto}")
    os.environ.setdefault(
        "URLS_AGENTES", ",".join(os.environ[variable] for variable in AGENTES_DEL_GRUPO)
    )


async def _esperar_arranque(servidores: dict[str, uvicorn.Server], tareas: list[asyncio.Task]) -> None:
    async with asyncio.timeout(TIMEOUT_ARRANQUE):
        while not all(servidor.started for servidor in servidores.values()):
            caidos = [nombre for (nombre, servidor), tarea in zip(servidores.items(), tareas) if tarea.done()]
            if caidos:
                raise RuntimeError(f"no arrancaron: {', '.join(caidos)}")
            await asyncio.sleep(0.2)


async def ejecutar() -> int:
    _configurar_entorno()
    servidores: dict[str, uvicorn.Server] = {}
    tareas: list[asyncio.Task] = []
    for nombre, modulo, puerto, _ in AGENTES:
        app = importlib.import_module(modulo).app
        servidor = _ServidorInterno(
            uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning", lifespan="on")
        )
        servidores[nombre] = servidor
        tareas.append(asyncio.create_task(servidor.serve(), name=nombre))

    try:
        await _esperar_arranque(servidores, tareas)
    except (TimeoutError, RuntimeError) as error:
        _registro.error("Los agentes no arrancaron: %s", error or "tiempo agotado")
        for servidor in servidores.values():
            servidor.should_exit = True
        await asyncio.gather(*tareas, return_exceptions=True)
        return 1
    _registro.info("Agentes listos: %s.", ", ".join(servidores))

    from api.app import app as api  # se importa después de fijar las URL

    puerto_api = int(os.environ.get("PORT", "8010"))
    servidor_api = uvicorn.Server(
        uvicorn.Config(api, host="0.0.0.0", port=puerto_api, proxy_headers=True, forwarded_allow_ips="*")
    )
    try:
        await servidor_api.serve()
    finally:
        for servidor in servidores.values():
            servidor.should_exit = True
        await asyncio.gather(*tareas, return_exceptions=True)
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    sys.exit(asyncio.run(ejecutar()))


if __name__ == "__main__":
    main()
