"""Evalúa las decisiones de enrutamiento del supervisor del coordinador."""

import asyncio
import json
from pathlib import Path

from src.coordinador.graph import decidir


ARCHIVO_CASOS = Path(__file__).resolve().parents[1] / "tests" / "casos_supervisor.json"


async def ejecutar_casos() -> list[tuple[str, str, str, bool, str]]:
    casos = json.loads(ARCHIVO_CASOS.read_text(encoding="utf-8"))
    filas = []
    for caso in casos:
        try:
            resultado = await decidir(caso["mensaje"])
            obtenido = resultado["agente"]
            motivo = resultado["motivo"]
        except Exception as error:
            motivo = " ".join(str(error).splitlines()).strip() or "error inesperado"
            obtenido = f"ERROR: {motivo}"
        filas.append(
            (
                caso["mensaje"],
                caso["esperado"],
                obtenido,
                obtenido == caso["esperado"],
                motivo,
            )
        )
    return filas


def _acortar(texto: str, ancho: int) -> str:
    return texto if len(texto) <= ancho else texto[: ancho - 1] + "…"


def main() -> None:
    filas = asyncio.run(ejecutar_casos())
    anchos = (48, 26, 26, 3, 54)
    titulos = ("Mensaje", "Esperado", "Obtenido", "OK", "Motivo")
    print(" | ".join(titulo.ljust(ancho) for titulo, ancho in zip(titulos, anchos)))
    print("-+-".join("-" * ancho for ancho in anchos))
    for mensaje, esperado, obtenido, acierto, motivo in filas:
        valores = (mensaje, esperado, obtenido, "✔" if acierto else "✘", motivo)
        print(" | ".join(_acortar(valor, ancho).ljust(ancho) for valor, ancho in zip(valores, anchos)))

    aciertos = sum(fila[3] for fila in filas)
    total = len(filas)
    porcentaje = 100 * aciertos / total if total else 0
    print(f"\nAciertos: {aciertos}/{total} ({porcentaje:.1f}%)")
    fallados = [fila for fila in filas if not fila[3]]
    print("Fallados:")
    if not fallados:
        print("Ninguno")
    for mensaje, esperado, obtenido, _, motivo in fallados:
        print(f"- {mensaje} | esperado: {esperado} | obtenido: {obtenido} | motivo: {motivo}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        detalle = " ".join(str(error).splitlines()).strip()
        print(f"No se pudo probar el supervisor: {detalle or 'error inesperado'}.")
