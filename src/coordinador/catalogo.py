"""Descubrimiento de agentes A2A configurados para el supervisor."""

import os

from dotenv import load_dotenv

from src.coordinador.cliente import FICHAS_POR_URL, obtener_cliente


def _urls_configuradas() -> list[str]:
    load_dotenv()
    urls = [
        os.getenv("URL_VIAJES", ""),
        os.getenv("URL_RESTAURANTES", ""),
        *os.getenv("URLS_AGENTES", "").split(","),
    ]
    resultado = []
    vistas = set()
    for url in urls:
        normalizada = url.strip().rstrip("/")
        if normalizada and normalizada not in vistas:
            vistas.add(normalizada)
            resultado.append(normalizada)
    return resultado


async def descubrir() -> list[dict]:
    """Descarga fichas y construye catálogo de agentes únicos por nombre."""
    agentes = []
    nombres_vistos = set()

    for url in _urls_configuradas():
        try:
            cliente = await obtener_cliente(url)
            tarjeta = FICHAS_POR_URL[url]
        except Exception as error:
            detalle = " ".join(str(error).splitlines()).strip()
            print(f"No se pudo cargar el agente en {url}: {detalle or 'error de conexión'}.")
            continue

        if tarjeta.name in nombres_vistos:
            print(f"Ficha duplicada para '{tarjeta.name}' en {url}; se conserva la primera.")
            continue
        nombres_vistos.add(tarjeta.name)
        agentes.append(
            {
                "nombre": tarjeta.name,
                "descripcion": tarjeta.description,
                "cliente": cliente,
                "url": url,
            }
        )

    return agentes
