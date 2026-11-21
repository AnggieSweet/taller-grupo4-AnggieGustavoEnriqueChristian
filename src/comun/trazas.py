"""Lo que imprimen --saltos y --diagrama, igual para todos los agentes LangGraph."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage


def _corto(texto: Any, n: int = 160) -> str:
    t = " ".join(str(texto).split())
    return t if len(t) <= n else t[: n - 1] + "…"


def imprimir_saltos(graph, entrada: dict, thread_id: str | None = None) -> dict:
    """Versión para la terminal (sin event loop corriendo)."""
    return asyncio.run(imprimir_saltos_async(graph, entrada, thread_id))


async def imprimir_saltos_async(graph, entrada: dict, thread_id: str | None = None, recursion_limit: int = 25) -> dict:
    """Corre el grafo con stream_mode="updates" e imprime cada nodo y cada herramienta.

    Devuelve un resumen {"saltos", "herramientas", "nodos", "final"} (lo usan los tests y promptfoo).
    """
    cfg = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}, "recursion_limit": recursion_limit}
    saltos, herramientas, nodos, final = 0, [], [], {}
    async for ns, actualizacion in graph.astream(entrada, cfg, stream_mode="updates", subgraphs=True):
        for nodo, datos in (actualizacion or {}).items():
            saltos += 1
            nodos.append(nodo)
            prefijo = "  " * len(ns)
            detalle = ""
            for m in (datos or {}).get("messages", []) if isinstance(datos, dict) else []:
                if isinstance(m, AIMessage) and m.tool_calls:
                    detalle = "llama a " + ", ".join(
                        f"{c['name']}({', '.join(f'{k}={json.dumps(v, ensure_ascii=False)}' for k, v in c['args'].items())})"
                        for c in m.tool_calls
                    )
                    herramientas += [c["name"] for c in m.tool_calls]
                elif isinstance(m, ToolMessage):
                    detalle = f'"{_corto(m.content)}"'
                elif isinstance(m, AIMessage):
                    detalle = "respuesta final" if not ns else f'"{_corto(m.text, 90)}"'
            if isinstance(datos, dict):
                for clave in ("veredicto", "categoria", "agente", "motivo", "revision"):
                    if clave in datos and datos[clave] not in (None, ""):
                        detalle += f" · {clave}={datos[clave]!r}"
            print(f"{prefijo}→ {nodo:<16}: {detalle.strip(' ·') or '(sin cambios)'}")
            if not ns and isinstance(datos, dict):
                final.update(datos)
    unicas = list(dict.fromkeys(herramientas))
    print(f"Saltos: {saltos} · Herramientas: {', '.join(unicas) or 'ninguna'}")
    texto = ultimo_texto(final)
    if texto:
        print(f"Respuesta: {texto}")
    return {"saltos": saltos, "herramientas": unicas, "nodos": nodos, "final": texto}


def imprimir_diagrama(graph) -> str:
    """Imprime el Mermaid del grafo sin ejecutarlo."""
    texto = graph.get_graph(xray=1).draw_mermaid()
    print(texto)
    return texto


def ultimo_texto(resultado: dict) -> str:
    """El texto del último mensaje del agente (o 'respuesta' si el grafo la guarda aparte)."""
    if resultado.get("respuesta"):
        return str(resultado["respuesta"])
    for m in reversed(resultado.get("messages", [])):
        if isinstance(m, AIMessage) and m.content:
            return m.text  # .text junta las partes de texto (Gemini puede devolver una lista)
    return ""
