"""Grafo LangGraph del agente de Anggie."""

import os
from collections.abc import Iterable
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver

from src.agente_anggie.prompts import SYSTEM_PROMPT
from src.agente_anggie.tools import buscar_productos, ver_ofertas


load_dotenv()
MODELO = os.getenv("MODELO", "gemini-3.5-flash-lite")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

_modelo = ChatGoogleGenerativeAI(
    model=MODELO,
    api_key=GOOGLE_API_KEY or "CLAVE_NO_CONFIGURADA",
    request_timeout=30,
)


class ForzarConsultaDeHerramienta(AgentMiddleware):
    """Exige una consulta inicial a herramientas para evitar respuestas inventadas."""

    def wrap_model_call(self, request, handler):
        if request.messages and request.messages[-1].type == "human":
            request = request.override(tool_choice="any")
        return handler(request)

    async def awrap_model_call(self, request, handler):
        if request.messages and request.messages[-1].type == "human":
            request = request.override(tool_choice="any")
        return await handler(request)


graph = create_agent(
    model=_modelo,
    tools=[buscar_productos, ver_ofertas],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=MemorySaver(),
    middleware=[ForzarConsultaDeHerramienta()],
)


def _texto_mensaje(mensaje: Any) -> str:
    contenido = mensaje.content
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, Iterable):
        return "\n".join(
            str(parte.get("text", "")) if isinstance(parte, dict) else str(parte)
            for parte in contenido
        ).strip()
    return str(contenido)


async def responder(texto: str, context_id: str) -> str:
    """Invoca el agente y conserva memoria asociada al identificador de contexto."""
    if not GOOGLE_API_KEY:
        raise RuntimeError("Falta GOOGLE_API_KEY; configura tu clave de Gemini en .env")
    resultado = await graph.ainvoke(
        {"messages": [{"role": "user", "content": texto}]},
        config={"configurable": {"thread_id": context_id}},
    )
    for mensaje in reversed(resultado.get("messages", [])):
        if isinstance(mensaje, AIMessage):
            return _texto_mensaje(mensaje)
    return "No se recibió una respuesta del agente de Anggie."


def saltos(texto: str) -> str:
    """Ejecuta el grafo e imprime nodos, herramientas y cantidad de saltos."""
    if not GOOGLE_API_KEY:
        raise RuntimeError("Falta GOOGLE_API_KEY; configura tu clave de Gemini en .env")
    cantidad_saltos = 0
    respuesta_final = ""
    eventos = graph.stream(
        {"messages": [{"role": "user", "content": texto}]},
        config={"configurable": {"thread_id": "terminal-anggie"}},
        stream_mode="updates",
    )
    for evento in eventos:
        for nombre_nodo, actualizacion in evento.items():
            cantidad_saltos += 1
            print(f"Nodo: {nombre_nodo}")
            for mensaje in actualizacion.get("messages", []):
                for llamada in getattr(mensaje, "tool_calls", []):
                    print(f"Herramienta: {llamada.get('name', 'desconocida')}")
                    print(f"Argumentos: {llamada.get('args', {})}")
                if isinstance(mensaje, AIMessage) and not mensaje.tool_calls:
                    respuesta_final = _texto_mensaje(mensaje)
    print(f"Total de saltos: {cantidad_saltos}")
    return respuesta_final


def diagrama() -> None:
    """Imprime el diagrama Mermaid del grafo sin ejecutarlo."""
    print(graph.get_graph().draw_mermaid())
