"""Herramientas del agente de cartelera."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool


DATA_FILE = Path(__file__).parent / "data" / "cartelera.json"


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


def _formatear_funcion(pelicula: dict[str, Any], funcion: dict[str, Any]) -> dict[str, Any]:
    return {
        "pelicula": pelicula["titulo"],
        "genero": pelicula["genero"],
        "clasificacion": pelicula["clasificacion"],
        "duracion_minutos": pelicula["duracion_minutos"],
        **funcion,
    }


@tool
def consultar_cartelera(
    fecha: str,
    pelicula: str = "",
    formato: str = "",
    idioma: str = "",
) -> str:
    """Consulta la cartelera por fecha y filtros opcionales."""
    resultados: list[dict[str, Any]] = []
    for pelicula_data in _cargar_cartelera():
        if pelicula and not _coincide(pelicula_data["titulo"], pelicula):
            continue
        for funcion in pelicula_data.get("funciones", []):
            if formato and not _coincide(funcion.get("formato", ""), formato):
                continue
            if idioma and not _coincide(funcion.get("idioma", ""), idioma):
                continue
            resultados.append(_formatear_funcion(pelicula_data, funcion))

    if not resultados:
        return f"No hay funciones registradas para los filtros indicados en la fecha {fecha}."
    return json.dumps(resultados, ensure_ascii=False)


@tool
def buscar_funciones(pelicula: str, fecha: str = "") -> str:
    """Busca las funciones de una película, opcionalmente por fecha."""
    if not pelicula.strip():
        return "Indica el nombre de una película para buscar sus funciones."

    resultados: list[dict[str, Any]] = []
    for pelicula_data in _cargar_cartelera():
        if not _coincide(pelicula_data["titulo"], pelicula):
            continue
        for funcion in pelicula_data.get("funciones", []):
            resultados.append(_formatear_funcion(pelicula_data, funcion))

    if not resultados:
        return f"No encontré funciones registradas para la película '{pelicula}'."
    return json.dumps(resultados, ensure_ascii=False)


TOOLS = [consultar_cartelera, buscar_funciones]
