"""Servidor A2A del agente de Anggie."""

import os

from dotenv import load_dotenv

from src.agente_anggie.graph import responder
from src.comun.servidor import crear_app
from src.comun.tarjeta import crear_tarjeta


load_dotenv()
URL_ANGGIE = os.getenv("URL_ANGGIE", "http://127.0.0.1:8003")

tarjeta = crear_tarjeta(
    "Agente de Anggie",
    "Respondo consultas sobre productos, precios, tallas, tonos, medidas, stock y ofertas de Calzado Paso Firme, Cosmética Brillo Natural, Mascotas Huella Feliz y Muebles Casa Serena, con filtro por presupuesto. No vendo comida para personas ni para mascotas, entradas de cine ni productos de supermercado, y no cobro, no reservo ni aparto productos.",
    URL_ANGGIE,
    [
        (
            "buscar_productos",
            "Productos del mall",
            "Consulta productos, precios, tallas, tonos, medidas y stock en las cuatro tiendas, con filtro de presupuesto.",
            "¿Qué tallas tiene el zapato de mujer y cuánto cuesta?",
        ),
        (
            "ver_ofertas",
            "Ofertas del mall",
            "Consulta productos en oferta en las cuatro tiendas, con filtros por tienda y precio máximo.",
            "¿Qué ofertas hay en muebles por menos de $200.000?",
        ),
    ],
)

app = crear_app(tarjeta, responder)
