"""Grafo LangGraph del agente de Anggie."""

from collections.abc import Iterable
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from src import config
from src.agente_anggie.prompts import SYSTEM_PROMPT
from src.agente_anggie.tools import buscar_productos, ver_ofertas
from src.comun.modelo import crear_llm_gemini


load_dotenv()


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


def _construir_grafo(permitir_sin_clave: bool = True):
    modelo = crear_llm_gemini(timeout=30.0, permitir_sin_clave_al_importar=permitir_sin_clave)
    return create_agent(
        model=modelo,
        tools=[buscar_productos, ver_ofertas],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
        middleware=[ForzarConsultaDeHerramienta()],
    )


graph = _construir_grafo(permitir_sin_clave=True)


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
    config.exigir_clave()
    resultado = await graph.ainvoke(
        {"messages": [{"role": "user", "content": texto}]},
        config={"configurable": {"thread_id": context_id}, "recursion_limit": config.MAX_PASOS_AGENTE * 2},
    )
    for mensaje in reversed(resultado.get("messages", [])):
        if isinstance(mensaje, AIMessage):
            return _texto_mensaje(mensaje)
    return "No se recibió una respuesta del agente de Anggie."


def saltos(texto: str) -> str:
    """Ejecuta el grafo e imprime nodos, herramientas y cantidad de saltos."""
    config.exigir_clave()
    cantidad_saltos = 0
    respuesta_final = ""
    eventos = graph.stream(
        {"messages": [{"role": "user", "content": texto}]},
        config={"configurable": {"thread_id": "terminal-anggie"}, "recursion_limit": config.MAX_PASOS_AGENTE * 2},
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
