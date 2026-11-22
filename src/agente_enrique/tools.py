"""Herramientas del agente de cartelera.

La cartelera de ejemplo es diaria: las mismas funciones se repiten todos los
días. Por eso la fecha guardada en el JSON no se muestra; cada resultado lleva
la fecha que pidió el usuario (o "todos los días" si no indicó una).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from langchain_core.tools import tool


DATA_FILE = Path(__file__).parent / "data" / "cartelera.json"
SIN_FECHA = "todos los días"


def _cargar_cartelera() -> list[dict[str, Any]]:
    try:
        with DATA_FILE.open(encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _normalizar(valor: str | None) -> str:
    return (valor or "").strip().casefold()


def _coincide(texto: str, filtro: str | None) -> bool:
    return not filtro or _normalizar(filtro) in _normalizar(texto)


def _validar_fecha(fecha: str) -> str | None:
    """Devuelve la fecha en formato AAAA-MM-DD, SIN_FECHA si viene vacía, o None si no es válida."""
    fecha = (fecha or "").strip()
    if not fecha:
        return SIN_FECHA
    try:
        return date.fromisoformat(fecha).isoformat()
    except ValueError:
        return None


def _formatear_funcion(pelicula: dict[str, Any], funcion: dict[str, Any], fecha: str) -> dict[str, Any]:
    datos_funcion = {clave: valor for clave, valor in funcion.items() if clave != "fecha"}
    return {
        "pelicula": pelicula["titulo"],
        "genero": pelicula["genero"],
        "clasificacion": pelicula["clasificacion"],
        "duracion_minutos": pelicula["duracion_minutos"],
        "fecha": fecha,
        **datos_funcion,
    }


@tool
def consultar_cartelera(
    fecha: str = "",
    pelicula: str = "",
    formato: str = "",
    idioma: str = "",
) -> str:
    """Consulta la cartelera con filtros opcionales.

    fecha: en formato AAAA-MM-DD (por ejemplo 2026-11-23); vacía si el usuario no indicó una.
    pelicula, formato (2D, IMAX) e idioma filtran por coincidencia parcial.
    """
    fecha_valida = _validar_fecha(fecha)
    if fecha_valida is None:
        return f"La fecha '{fecha}' no es válida; usa el formato AAAA-MM-DD."

    resultados: list[dict[str, Any]] = []
    for pelicula_data in _cargar_cartelera():
        if pelicula and not _coincide(pelicula_data["titulo"], pelicula):
            continue
        for funcion in pelicula_data.get("funciones", []):
            if formato and not _coincide(funcion.get("formato", ""), formato):
                continue
            if idioma and not _coincide(funcion.get("idioma", ""), idioma):
                continue
            resultados.append(_formatear_funcion(pelicula_data, funcion, fecha_valida))

    if not resultados:
        return "No hay funciones registradas para los filtros indicados."
    return json.dumps(resultados, ensure_ascii=False)


@tool
def buscar_funciones(pelicula: str, fecha: str = "") -> str:
    """Busca las funciones de una película.

    fecha: en formato AAAA-MM-DD (por ejemplo 2026-11-23); vacía si el usuario no indicó una.
    """
    if not pelicula.strip():
        return "Indica el nombre de una película para buscar sus funciones."
    fecha_valida = _validar_fecha(fecha)
    if fecha_valida is None:
        return f"La fecha '{fecha}' no es válida; usa el formato AAAA-MM-DD."

    resultados: list[dict[str, Any]] = []
    for pelicula_data in _cargar_cartelera():
        if not _coincide(pelicula_data["titulo"], pelicula):
            continue
        for funcion in pelicula_data.get("funciones", []):
            resultados.append(_formatear_funcion(pelicula_data, funcion, fecha_valida))

    if not resultados:
        return f"No encontré funciones registradas para la película '{pelicula}'."
    return json.dumps(resultados, ensure_ascii=False)


TOOLS = [consultar_cartelera, buscar_funciones]
