"""Servidor A2A del agente de Enrique, con el mismo molde que los demás agentes."""

import asyncio
import os

from dotenv import load_dotenv

from src.agente_enrique.graph import responder as responder_sync
from src.comun.servidor import crear_app
from src.comun.tarjeta import crear_tarjeta

load_dotenv()

URL_ENRIQUE = os.getenv("URL_ENRIQUE", "http://127.0.0.1:8004")


async def responder(texto: str, context_id: str) -> str:
    """Contrato común: ejecuta el responder sincrónico de Enrique sin bloquear el servidor."""
    return await asyncio.to_thread(responder_sync, texto, context_id)


tarjeta = crear_tarjeta(
    nombre="Agente de Enrique",
    descripcion=(
        "Responde consultas sobre la cartelera de este cine: películas en "
        "exhibición, funciones por fecha, horarios, salas, formatos 2D o IMAX, "
        "idioma, subtítulos, clasificación y precios registrados. No compra ni "
        "reserva entradas, no procesa pagos y no responde sobre otros temas."
    ),
    url=URL_ENRIQUE,
    skills=[
        (
            "consultar_cartelera",
            "Consultar cartelera",
            "Consulta las películas y funciones registradas para una fecha, con filtros opcionales de película, formato o idioma.",
            "¿Qué películas hay en cartelera el 10 de noviembre?",
        ),
        (
            "buscar_funciones",
            "Buscar funciones",
            "Busca los horarios, salas, formatos, idiomas y precios registrados para una película específica.",
            "¿A qué hora dan Duna: Parte Dos?",
        ),
    ],
)

app = crear_app(tarjeta, responder)