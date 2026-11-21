"""Punto de entrada para ejecutar agentes desde la terminal."""

import argparse
import asyncio
import inspect


def main():
    parser = argparse.ArgumentParser(description="Ejecuta un agente del proyecto.")
    parser.add_argument(
        "agente",
        choices=("viajes", "anggie", "restaurantes", "coordinador", "enrique", "algomarket", "christian"),
    )
    parser.add_argument("pregunta", nargs="?", default="")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--saltos", action="store_true")
    modo.add_argument("--diagrama", action="store_true")
    argumentos = parser.parse_args()

    nombre_agente = {
        "viajes": "viajes",
        "anggie": "Anggie",
        "restaurantes": "restaurantes",
        "coordinador": "Coordinador",
        "enrique": "Enrique",
        "algomarket": "Algomarket",
        "christian": "Christian",
    }[argumentos.agente]
    try:
        if argumentos.agente == "viajes":
            from src.agente_viajes.graph import diagrama, responder, saltos
        elif argumentos.agente == "anggie":
            from src.agente_anggie.graph import diagrama, responder, saltos
        elif argumentos.agente == "restaurantes":
            from src.agente_restaurantes.crew import diagrama, responder, saltos
        elif argumentos.agente == "enrique":
            from src.agente_enrique.graph import diagrama, responder, saltos
        elif argumentos.agente == "algomarket":
            from src.agente_algomarket.graph import diagrama, responder, saltos
        elif argumentos.agente == "christian":
            from src.agente_christian.graph import diagrama, responder, saltos_async as saltos
        else:
            from src.coordinador.graph import diagrama, responder, saltos

        if argumentos.diagrama:
            resultado = diagrama()
            if resultado and argumentos.agente != "christian":
                print(resultado)
        elif argumentos.saltos:
            respuesta = saltos(argumentos.pregunta)
            if inspect.isawaitable(respuesta):
                respuesta = asyncio.run(respuesta)
            if respuesta:
                print(respuesta)
        else:
            respuesta = responder(argumentos.pregunta, f"terminal-{argumentos.agente}")
            if inspect.isawaitable(respuesta):
                respuesta = asyncio.run(respuesta)
            print(respuesta)
    except Exception as error:
        detalle = " ".join(str(error).splitlines()).strip()
        print(f"No se pudo ejecutar el agente de {nombre_agente}: {detalle or 'error inesperado'}.")


if __name__ == "__main__":
    main()
