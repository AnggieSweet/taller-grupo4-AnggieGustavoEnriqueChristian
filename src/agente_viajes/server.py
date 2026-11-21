"""Servidor HTTP A2A del agente de viajes."""

import os

from dotenv import load_dotenv

from src.agente_viajes.graph import responder
from src.comun.servidor import crear_app
from src.comun.tarjeta import crear_tarjeta


load_dotenv()
URL_VIAJES = os.getenv("URL_VIAJES", "http://127.0.0.1:8000")

tarjeta = crear_tarjeta(
    "Agente de viajes",
    "Busca vuelos y hoteles entre SCL, LIM, BOG y EZE con precios en CLP. No reserva ni cobra.",
    URL_VIAJES,
    [
        (
            "buscar_vuelos",
            "Buscar vuelos",
            "Consulta vuelos ficticios entre SCL, LIM, BOG y EZE con fecha y precio en CLP.",
            "Busca un vuelo de SCL a LIM para el 15 de agosto.",
        ),
        (
            "buscar_hoteles",
            "Buscar hoteles",
            "Consulta hoteles ficticios por ciudad, cantidad de noches y precio en CLP.",
            "Encuentra hotel en Lima por tres noches.",
        ),
    ],
)

app = crear_app(tarjeta, responder)
