"""Grafo LangGraph del agente de Enrique."""

from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src import config
from src.comun.modelo import crear_llm_gemini

from .prompts import SYSTEM_PROMPT
from .tools import TOOLS

load_dotenv()

DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
# Cada vuelta modelo → herramienta son dos pasos del grafo.
LIMITE_PASOS = config.MAX_PASOS_AGENTE * 2


def _prompt_sistema() -> str:
    """Completa el prompt con la fecha de hoy (AHORA en .env la fija para pruebas)."""
    hoy = config.ahora().date()
    return SYSTEM_PROMPT.format(hoy=hoy.isoformat(), dia_semana=DIAS_SEMANA[hoy.weekday()])


def crear_agente():
    """Crea y compila el agente con memoria en el proceso."""
    model = crear_llm_gemini(temperatura=0.0, timeout=30.0, permitir_sin_clave_al_importar=True).bind_tools(TOOLS)

    def llamar_modelo(state: MessagesState) -> dict[str, Any]:
        mensajes = [{"role": "system", "content": _prompt_sistema()}, *state["messages"]]
        respuesta = model.invoke(mensajes)
        return {"messages": [respuesta]}

    builder = StateGraph(MessagesState)
    builder.add_node("model", llamar_modelo)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", tools_condition)
    builder.add_edge("tools", "model")

    return builder.compile(checkpointer=MemorySaver())


_AGENT = None


def _agente():
    global _AGENT
    if _AGENT is None:
        _AGENT = crear_agente()
    return _AGENT


def responder(texto: str, context_id: str = "enrique-local") -> str:
    """Responde una pregunta conservando el contexto indicado."""
    config.exigir_clave()
    resultado = _agente().invoke(
        {"messages": [{"role": "user", "content": texto}]},
        {"configurable": {"thread_id": context_id}, "recursion_limit": LIMITE_PASOS},
    )
    contenido = resultado["messages"][-1].content
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "".join(
            parte.get("text", "")
            for parte in contenido
            if isinstance(parte, dict)
        )
    return str(contenido)


def saltos(texto: str, context_id: str = "enrique-local") -> list[str]:
    """Devuelve una descripción simple de los nodos visitados."""
    config.exigir_clave()
    pasos: list[str] = []
    for evento in _agente().stream(
        {"messages": [{"role": "user", "content": texto}]},
        {"configurable": {"thread_id": context_id}, "recursion_limit": LIMITE_PASOS},
        stream_mode="updates",
    ):
        pasos.extend(evento.keys())
    return pasos


def diagrama() -> str:
    return "graph TD; __start__ --> model; model -. tools .-> tools; tools --> model; model -. end .-> __end__"
