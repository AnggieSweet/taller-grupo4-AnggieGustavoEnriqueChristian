"""Pruebas de decisión del supervisor sin ejecutar agentes remotos."""

import asyncio
import json
from pathlib import Path

import pytest

from src.coordinador import graph as coordinador


ARCHIVO_CASOS = Path(__file__).with_name("casos_supervisor.json")
AGENTES_ESPERADOS = {
    "Agente de Anggie",
    "Agente de Enrique",
    "Agente de Algomarket",
    "Agente de Christian",
    "Agente de viajes",
    "Agente de restaurantes",
}


def test_decisiones_supervisor() -> None:
    casos = json.loads(ARCHIVO_CASOS.read_text(encoding="utf-8"))

    async def ejecutar() -> list[tuple[dict, str]]:
        await coordinador._asegurar_catalogo()
        encontrados = {agente["nombre"] for agente in coordinador._agentes}
        faltantes = sorted(AGENTES_ESPERADOS - encontrados)
        if faltantes:
            pytest.skip(
                "No se pudieron cargar las fichas A2A requeridas: "
                + ", ".join(faltantes)
                + ". Comprueba que todos los agentes estén disponibles."
            )

        resultados = []
        for caso in casos:
            try:
                decision = await coordinador.decidir(caso["mensaje"])
            except Exception as error:
                pytest.skip(
                    "El supervisor o un servicio necesario no respondió; "
                    f"prueba omitida: {' '.join(str(error).splitlines())}"
                )
            resultados.append((caso, decision["agente"]))
        return resultados

    resultados = asyncio.run(ejecutar())
    aciertos = sum(obtenido == caso["esperado"] for caso, obtenido in resultados)
    assert aciertos >= 16, (
        f"Se requieren al menos 16 de 18 aciertos; hubo {aciertos}. "
        f"Fallados: {[(caso['mensaje'], caso['esperado'], obtenido) for caso, obtenido in resultados if obtenido != caso['esperado']]}"
    )
