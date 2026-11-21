"""Prueba el enrutamiento del supervisor mediante el protocolo A2A."""

import asyncio
import os
import re
import textwrap
from uuid import uuid4

from dotenv import load_dotenv

from src.coordinador.cliente import obtener_cliente, preguntar


PREGUNTAS = [
    "¿Qué vuelos hay de SCL a LIM el 20 de diciembre de 2026?",
    "¿Qué hoteles hay en Lima para tres noches?",
    "¿Qué tallas tiene el zapato de mujer?",
    "¿Qué ofertas hay en muebles?",
    "Busco una cama en Santiago, ¿qué opciones tengo?",
    "¿Qué horarios tiene el cine?",
]


def _interpretar_respuesta(texto: str) -> tuple[str, str, str]:
    encabezado = re.match(r"^\[([^\]]+)\]\s+Motivo:\s*([^\r\n]*)", texto)
    if encabezado:
        agente, motivo = encabezado.groups()
        inicio = texto[encabezado.end():].strip().splitlines()
        return agente, motivo, inicio[0] if inicio else ""

    sin_agente = re.search(r"Motivo del supervisor:\s*([^\r\n]*)", texto)
    motivo = sin_agente.group(1) if sin_agente else "No hay un agente adecuado."
    inicio = texto.splitlines()[0] if texto else ""
    return "ninguno", motivo, inicio


async def main() -> None:
    load_dotenv()
    url = os.getenv("URL_COORDINADOR", "http://127.0.0.1:8002")
    cliente = await obtener_cliente(url)
    filas = []
    for pregunta in PREGUNTAS:
        respuesta = await preguntar(cliente, pregunta, str(uuid4()))
        agente, motivo, inicio = _interpretar_respuesta(respuesta)
        filas.append((pregunta, agente, motivo, inicio))

    anchos = (34, 22, 42, 48)
    encabezados = ("Pregunta", "Agente elegido", "Motivo", "Inicio de respuesta")
    print(" | ".join(t.ljust(a) for t, a in zip(encabezados, anchos, strict=True)))
    print("-+-".join("-" * ancho for ancho in anchos))
    for fila in filas:
        celdas = [
            textwrap.shorten(valor, width=ancho, placeholder="…").ljust(ancho)
            for valor, ancho in zip(fila, anchos, strict=True)
        ]
        print(" | ".join(celdas))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        detalle = " ".join(str(error).splitlines()).strip()
        print(f"No se pudo probar el supervisor: {detalle or 'error inesperado'}.")
