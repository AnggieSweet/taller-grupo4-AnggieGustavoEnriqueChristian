"""Servidor A2A del supervisor."""

import os

from dotenv import load_dotenv

from src.comun.servidor import crear_app
from src.comun.tarjeta import crear_tarjeta
from src.coordinador.catalogo import descubrir
from src.coordinador.graph import establecer_catalogo, responder


load_dotenv()
URL_COORDINADOR = os.getenv("URL_COORDINADOR", "http://127.0.0.1:8002")

tarjeta = crear_tarjeta(
    "Coordinador",
    "Clasifica preguntas y las dirige al agente A2A adecuado según las fichas disponibles. Si ningún agente cubre la consulta, informa qué temas puede atender el catálogo.",
    URL_COORDINADOR,
    [
        (
            "enrutar_preguntas",
            "Enrutar preguntas",
            "Selecciona un agente del catálogo y transmite la pregunta por A2A.",
            "¿Qué ofertas hay en muebles?",
        ),
    ],
)

app = crear_app(tarjeta, responder)


async def _iniciar_supervisor() -> None:
    agentes = await descubrir()
    establecer_catalogo(agentes)
    print(f"Supervisor con {len(agentes)} agentes")


app.router.add_event_handler("startup", _iniciar_supervisor)
