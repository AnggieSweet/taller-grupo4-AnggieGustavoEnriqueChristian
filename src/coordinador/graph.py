"""Grafo LangGraph supervisor que enruta preguntas a agentes A2A."""

import asyncio
import os
import unicodedata
from collections.abc import Iterable
from typing import Annotated, Any, NotRequired, TypedDict
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, field_validator

from src.coordinador.catalogo import descubrir
from src.coordinador.cliente import preguntar
from src.coordinador.prompts import PROMPT_SUPERVISOR


load_dotenv()
MODELO = os.getenv("MODELO", "gemini-3.5-flash-lite")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
_modelo = ChatGoogleGenerativeAI(
    model=MODELO,
    api_key=GOOGLE_API_KEY or "CLAVE_NO_CONFIGURADA",
    temperature=0,
    request_timeout=30,
)
_agentes: list[dict] = []


class Decision(BaseModel):
    """Decisión de enrutamiento del supervisor."""

    agente: str = Field(description="Nombre exacto de un agente del catálogo o 'ninguno'.")
    motivo: str = Field(description="Una frase breve que justifica la elección.")

    @field_validator("agente")
    @classmethod
    def validar_agente(cls, agente: str) -> str:
        def normalizar(nombre: str) -> str:
            sin_tildes = "".join(
                caracter
                for caracter in unicodedata.normalize("NFD", nombre)
                if unicodedata.category(caracter) != "Mn"
            ).casefold().strip()
            if sin_tildes.startswith("agente de "):
                sin_tildes = sin_tildes[len("agente de "):].strip()
            return sin_tildes

        if normalizar(agente) == "ninguno":
            return "ninguno"
        nombres = {registro["nombre"] for registro in _agentes}
        coincidencias = [nombre for nombre in nombres if normalizar(nombre) == normalizar(agente)]
        if len(coincidencias) == 1:
            return coincidencias[0]
        raise ValueError("El agente elegido debe existir en el catálogo o ser 'ninguno'.")


class Estado(TypedDict):
    """Estado conversacional del supervisor."""

    messages: Annotated[list, add_messages]
    agente: NotRequired[str]
    motivo: NotRequired[str]
    respuesta: NotRequired[str]


def establecer_catalogo(agentes: list[dict]) -> None:
    """Actualiza la lista que el grafo usa para validar decisiones."""
    global _agentes
    _agentes = agentes


def _pregunta_actual(estado: Estado) -> str:
    for mensaje in reversed(estado["messages"]):
        if isinstance(mensaje, HumanMessage):
            return str(mensaje.content)
    return ""


async def _nodo_supervisor(estado: Estado) -> dict:
    pregunta = _pregunta_actual(estado)
    descripciones = "\n".join(
        f"- {agente['nombre']}: {agente['descripcion']}"
        for agente in _agentes
    ) or "(No hay agentes disponibles.)"
    prompt = PROMPT_SUPERVISOR.format(catalogo=descripciones)
    if not GOOGLE_API_KEY:
        raise RuntimeError("Falta GOOGLE_API_KEY; configura tu clave de Gemini en .env")
    decision = await _modelo.with_structured_output(Decision).ainvoke(
        [
            SystemMessage(content=prompt),
            HumanMessage(
                content=(
                    "Últimos mensajes del thread (máximo 6):\n"
                    f"{_historial_reciente(estado)}\n\n"
                    f"Pregunta actual:\n{pregunta}"
                )
            ),
        ]
    )
    return {"agente": decision.agente, "motivo": decision.motivo}


def _historial_reciente(estado: Estado) -> str:
    """Devuelve los últimos seis mensajes conversacionales como contexto."""
    mensajes = estado["messages"][-6:]
    lineas = []
    for mensaje in mensajes:
        if isinstance(mensaje, HumanMessage):
            rol = "Usuario"
        elif isinstance(mensaje, AIMessage):
            rol = "Coordinador/agente"
        else:
            continue
        lineas.append(f"{rol}: {mensaje.content}")
    return "\n".join(lineas) or "(sin historial previo)"


async def _nodo_agente_remoto(estado: Estado, config: RunnableConfig) -> dict:
    nombre = estado["agente"]
    agente = next(item for item in _agentes if item["nombre"] == nombre)
    context_id = config.get("configurable", {}).get("thread_id") or str(uuid4())
    try:
        respuesta = await preguntar(
            agente["cliente"],
            _pregunta_actual(estado),
            context_id,
        )
    except Exception as error:
        detalle = " ".join(str(error).splitlines()).strip()
        respuesta = f"No se pudo contactar al agente: {detalle or 'error inesperado'}."
    mensaje = AIMessage(
        content=f"[{nombre}] Motivo: {estado['motivo']}\n{respuesta}"
    )
    return {"messages": [mensaje], "respuesta": respuesta}


def _nodo_sin_agente(estado: Estado) -> dict:
    nombres = ", ".join(agente["nombre"] for agente in _agentes) or "ninguno disponible"
    mensaje = AIMessage(
        content=(
            f"No tengo un agente para eso. Puedo ayudarte con: {nombres}. "
            f"Motivo del supervisor: {estado['motivo']}"
        )
    )
    return {"messages": [mensaje], "respuesta": str(mensaje.content)}


def _ruta_supervisor(estado: Estado) -> str:
    return "sin_agente" if estado["agente"] == "ninguno" else "agente_remoto"


_constructor = StateGraph(Estado)
_constructor.add_node("supervisor", _nodo_supervisor)
_constructor.add_node("agente_remoto", _nodo_agente_remoto)
_constructor.add_node("sin_agente", _nodo_sin_agente)
_constructor.add_edge(START, "supervisor")
_constructor.add_conditional_edges(
    "supervisor",
    _ruta_supervisor,
    {"agente_remoto": "agente_remoto", "sin_agente": "sin_agente"},
)
_constructor.add_edge("agente_remoto", END)
_constructor.add_edge("sin_agente", END)
graph = _constructor.compile(checkpointer=MemorySaver())


def _ultimo_texto(estado: dict[str, Any]) -> str:
    for mensaje in reversed(estado.get("messages", [])):
        if isinstance(mensaje, AIMessage):
            contenido = mensaje.content
            if isinstance(contenido, str):
                return contenido
            if isinstance(contenido, Iterable):
                return "\n".join(
                    str(parte.get("text", "")) if isinstance(parte, dict) else str(parte)
                    for parte in contenido
                ).strip()
    return "El supervisor no recibió una respuesta."


async def _asegurar_catalogo() -> None:
    if not _agentes:
        establecer_catalogo(await descubrir())


async def decidir(texto: str) -> dict[str, str]:
    """Devuelve la decisión del supervisor sin invocar al agente elegido."""
    await _asegurar_catalogo()
    cambios = await _nodo_supervisor(
        {"messages": [HumanMessage(content=texto)]}
    )
    return {"agente": cambios["agente"], "motivo": cambios["motivo"]}


async def consultar(texto: str, thread_id: str) -> dict[str, str]:
    """Consulta al coordinador y devuelve la decisión y respuesta estructuradas."""
    await _asegurar_catalogo()
    estado = await graph.ainvoke(
        {"messages": [HumanMessage(content=texto)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "agente": estado.get("agente", "ninguno"),
        "motivo": estado.get("motivo", "Sin motivo disponible."),
        "respuesta": estado.get("respuesta") or _ultimo_texto(estado),
    }


async def responder(texto: str, context_id: str) -> str:
    """Ejecuta el supervisor para una pregunta y devuelve el texto final."""
    resultado = await consultar(texto, context_id)
    if resultado["agente"] == "ninguno":
        return resultado["respuesta"]
    return (
        f"[{resultado['agente']}] Motivo: {resultado['motivo']}\n"
        f"{resultado['respuesta']}"
    )


async def saltos(texto: str) -> str:
    """Imprime el recorrido del grafo, la decisión y el número de nodos."""
    await _asegurar_catalogo()
    cantidad = 0
    respuesta = ""
    async for evento in graph.astream(
        {"messages": [HumanMessage(content=texto)]},
        config={"configurable": {"thread_id": "terminal-coordinador"}},
        stream_mode="updates",
    ):
        for nombre_nodo, cambios in evento.items():
            cantidad += 1
            print(f"Paso: {nombre_nodo}")
            if nombre_nodo == "supervisor":
                print(f"Agente elegido: {cambios.get('agente', 'ninguno')}")
                print(f"Motivo: {cambios.get('motivo', 'sin motivo')}")
            for mensaje in cambios.get("messages", []):
                if isinstance(mensaje, AIMessage):
                    respuesta = str(mensaje.content)
    print(f"Total de saltos: {cantidad}")
    return respuesta


def diagrama() -> None:
    """Imprime el diagrama Mermaid del supervisor."""
    print(graph.get_graph().draw_mermaid())
