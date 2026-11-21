"""Comprueba el contexto de conversación independiente por thread del coordinador."""

import asyncio

from src.coordinador.graph import consultar


async def main() -> None:
    casos = [
        ("prueba-1", "¿Tienen zapatos de mujer?"),
        ("prueba-1", "¿Y qué tallas tiene?"),
        ("prueba-2", "¿Y qué tallas tiene?"),
    ]
    for thread_id, texto in casos:
        resultado = await consultar(texto, thread_id)
        print(f"Thread: {thread_id}")
        print(f"Pregunta: {texto}")
        print(f"Agente: {resultado['agente']}")
        print(f"Motivo: {resultado['motivo']}")
        print(f"Respuesta: {resultado['respuesta']}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        detalle = " ".join(str(error).splitlines()).strip()
        print(f"No se pudo probar la memoria: {detalle or 'error inesperado'}.")
