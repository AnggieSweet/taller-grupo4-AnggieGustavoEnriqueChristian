"""Grafo LangGraph supervisor que enruta e integra consultas entre uno o varios agentes A2A."""

import asyncio
import time
import unicodedata
from collections.abc import Iterable
from typing import Annotated, Any, NotRequired, TypedDict
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, field_validator

from src import config as app_config
from src.comun.guardias import verificar_fidelidad_integracion
from src.comun.modelo import crear_llm_gemini
from src.coordinador.catalogo import descubrir
from src.coordinador.cliente import preguntar
from src.coordinador.prompts import PROMPT_INTEGRADOR, PROMPT_SUPERVISOR


load_dotenv()
_agentes: list[dict] = []


def _normalizar_nombre_agente(nombre: str) -> str:
    sin_tildes = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", nombre)
        if unicodedata.category(caracter) != "Mn"
    ).casefold().strip()
    if sin_tildes.startswith("agente de "):
        sin_tildes = sin_tildes[len("agente de ") :].strip()
    return sin_tildes


class SubconsultaAgente(BaseModel):
    """Subconsulta contextualizada opcional para un agente específico."""

    agente: str = Field(description="Nombre exacto del agente destinatario.")
    pregunta: str = Field(description="Pregunta autocontenida para ese agente, conservando cifras y condiciones del usuario.")


class Decision(BaseModel):
    """Decisión de enrutamiento (simple o multi-agente) y detección de datos faltantes."""

    agentes: list[str] = Field(
        default_factory=lambda: ["ninguno"],
        description="Lista con uno o más nombres exactos de agentes del catálogo, o ['ninguno'].",
    )
    motivo: str = Field(description="Una frase breve que justifica la elección.")
    faltan_datos: bool = Field(
        default=False,
        description="True solo si faltan datos obligatorios (ej. ciudad y noches al pedir cotizar un hotel sin datos).",
    )
    pregunta_aclaracion: str = Field(
        default="",
        description="Si faltan_datos es True, pregunta breve y amable pidiendo los datos faltantes antes de concluir.",
    )
    subconsultas: list[SubconsultaAgente] = Field(
        default_factory=list,
        description="Subconsultas opcionales por agente cuando hay múltiples temas o contexto previo.",
    )

    @field_validator("agentes", mode="before")
    @classmethod
    def normalizar_entrada_agentes(cls, valor: Any) -> list[str]:
        if isinstance(valor, str):
            partes = [p.strip() for p in valor.split(",") if p.strip()]
            return partes or ["ninguno"]
        if isinstance(valor, list):
            return [str(x).strip() for x in valor if str(x).strip()] or ["ninguno"]
        return ["ninguno"]

    @field_validator("agentes")
    @classmethod
    def validar_agentes(cls, lista_agentes: list[str]) -> list[str]:
        if len(lista_agentes) == 1 and _normalizar_nombre_agente(lista_agentes[0]) == "ninguno":
            return ["ninguno"]

        nombres_catalogo = {registro["nombre"] for registro in _agentes}
        resueltos: list[str] = []
        for candidato in lista_agentes:
            if _normalizar_nombre_agente(candidato) == "ninguno":
                continue
            coincidencias = [
                nombre
                for nombre in nombres_catalogo
                if _normalizar_nombre_agente(nombre) == _normalizar_nombre_agente(candidato)
            ]
            if len(coincidencias) != 1:
                raise ValueError(f"El agente '{candidato}' debe existir en el catálogo o ser 'ninguno'.")
            if coincidencias[0] not in resueltos:
                resueltos.append(coincidencias[0])

        return resueltos or ["ninguno"]


class Estado(TypedDict):
    """Estado conversacional del supervisor."""

    messages: Annotated[list, add_messages]
    agentes: NotRequired[list[str]]
    agente: NotRequired[str]
    motivo: NotRequired[str]
    faltan_datos: NotRequired[bool]
    pregunta_aclaracion: NotRequired[str]
    subconsultas: NotRequired[dict[str, str]]
    aportes: NotRequired[list[dict[str, Any]]]
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


def _texto_contenido(contenido: Any) -> str:
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, Iterable):
        return "\n".join(
            str(parte.get("text", "")) if isinstance(parte, dict) else str(parte)
            for parte in contenido
        ).strip()
    return str(contenido)


async def _nodo_supervisor(estado: Estado) -> dict:
    app_config.exigir_clave()
    pregunta = _pregunta_actual(estado)
    descripciones = "\n".join(
        f"- {agente['nombre']}: {agente['descripcion']}"
        for agente in _agentes
    ) or "(No hay agentes disponibles.)"
    prompt = PROMPT_SUPERVISOR.format(catalogo=descripciones)
    modelo = crear_llm_gemini(temperatura=0.0, timeout=30.0)
    decision: Decision = await modelo.with_structured_output(Decision).ainvoke(
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

    mapa_sub: dict[str, str] = {}
    for item in decision.subconsultas:
        for ag in decision.agentes:
            if _normalizar_nombre_agente(item.agente) == _normalizar_nombre_agente(ag) and item.pregunta.strip():
                mapa_sub[ag] = item.pregunta.strip()

    etiqueta_agente = (
        "ninguno"
        if decision.agentes == ["ninguno"]
        else " + ".join(decision.agentes)
    )
    return {
        "agentes": decision.agentes,
        "agente": etiqueta_agente,
        "motivo": decision.motivo,
        "faltan_datos": decision.faltan_datos,
        "pregunta_aclaracion": decision.pregunta_aclaracion.strip(),
        "subconsultas": mapa_sub,
    }


def _nodo_pedir_datos(estado: Estado) -> dict:
    aclaracion = estado.get("pregunta_aclaracion") or (
        "Para darte una respuesta exacta sin asumir datos, ¿podrías indicarme los detalles faltantes de tu consulta?"
    )
    mensaje = AIMessage(content=aclaracion)
    return {"messages": [mensaje], "respuesta": aclaracion}


async def _consultar_uno(agente_info: dict, consulta_enviada: str, context_id: str) -> dict[str, Any]:
    inicio = time.perf_counter()
    try:
        texto = await preguntar(agente_info["cliente"], consulta_enviada, context_id)
        latencia_ms = round((time.perf_counter() - inicio) * 1000)
        fallo = texto.strip().lower().startswith(
            ("no se pudo contactar al agente:", "no se pudo procesar el mensaje:", "error al procesar la recomendación:")
        )
        return {
            "nombre": agente_info["nombre"],
            "consulta": consulta_enviada,
            "respuesta": texto,
            "ok": not fallo,
            "latencia_ms": latencia_ms,
        }
    except Exception as error:
        latencia_ms = round((time.perf_counter() - inicio) * 1000)
        detalle = " ".join(str(error).splitlines()).strip()
        return {
            "nombre": agente_info["nombre"],
            "consulta": consulta_enviada,
            "respuesta": f"No se pudo contactar al agente: {detalle or 'error inesperado'}.",
            "ok": False,
            "latencia_ms": latencia_ms,
        }


async def _nodo_agentes_remotos(estado: Estado, config: RunnableConfig) -> dict:
    nombres = estado.get("agentes") or [estado.get("agente", "ninguno")]
    pregunta_base = _pregunta_actual(estado)
    subconsultas = estado.get("subconsultas") or {}
    context_id = config.get("configurable", {}).get("thread_id") or str(uuid4())

    tareas = []
    for nombre in nombres:
        agente_info = next(item for item in _agentes if item["nombre"] == nombre)
        texto_enviar = subconsultas.get(nombre) or pregunta_base
        tareas.append(_consultar_uno(agente_info, texto_enviar, context_id))

    aportes = list(await asyncio.gather(*tareas))

    # Si algún agente falló, propagamos el texto de fallo para que la API devuelva 502/504 y nunca 200 engañoso.
    fallidos = [a for a in aportes if not a["ok"]]
    if fallidos:
        primero = fallidos[0]["respuesta"]
        return {"aportes": aportes, "respuesta": primero, "messages": [AIMessage(content=primero)]}

    if len(aportes) == 1:
        unico = aportes[0]
        mensaje = AIMessage(content=f"[{unico['nombre']}] Motivo: {estado['motivo']}\n{unico['respuesta']}")
        return {"aportes": aportes, "respuesta": unico["respuesta"], "messages": [mensaje]}

    return {"aportes": aportes}


async def _nodo_integrador(estado: Estado) -> dict:
    aportes = estado.get("aportes") or []
    reportes_fuente = [a["respuesta"] for a in aportes]
    bloques = "\n\n".join(f"=== {a['nombre']} ===\n{a['respuesta']}" for a in aportes)

    modelo = crear_llm_gemini(temperatura=0.0, timeout=30.0)
    respuesta_llm = await modelo.ainvoke(
        [HumanMessage(content=PROMPT_INTEGRADOR.format(pregunta=_pregunta_actual(estado), reportes=bloques))]
    )
    integrado = _texto_contenido(respuesta_llm.content).strip()

    fiel, _ = verificar_fidelidad_integracion(integrado, reportes_fuente)
    if not fiel or not integrado:
        # Respaldo determinista literal: conserva el 100 % de cifras, unidades y condiciones de cada agente.
        integrado = "\n\n".join(f"• {a['nombre']}: {a['respuesta']}" for a in aportes)

    etiqueta = estado.get("agente") or " + ".join(a["nombre"] for a in aportes)
    mensaje = AIMessage(content=f"[{etiqueta}] Motivo: {estado.get('motivo', '')}\n{integrado}")
    return {"respuesta": integrado, "messages": [mensaje]}


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
    if estado.get("faltan_datos"):
        return "pedir_datos"
    agentes = estado.get("agentes") or ["ninguno"]
    if agentes == ["ninguno"]:
        return "sin_agente"
    return "agentes_remotos"


def _ruta_tras_remotos(estado: Estado) -> str:
    aportes = estado.get("aportes") or []
    if any(not a["ok"] for a in aportes) or len(aportes) <= 1:
        return END
    return "integrador"


_constructor = StateGraph(Estado)
_constructor.add_node("supervisor", _nodo_supervisor)
_constructor.add_node("pedir_datos", _nodo_pedir_datos)
_constructor.add_node("agentes_remotos", _nodo_agentes_remotos)
_constructor.add_node("integrador", _nodo_integrador)
_constructor.add_node("sin_agente", _nodo_sin_agente)
_constructor.add_edge(START, "supervisor")
_constructor.add_conditional_edges(
    "supervisor",
    _ruta_supervisor,
    {
        "pedir_datos": "pedir_datos",
        "agentes_remotos": "agentes_remotos",
        "sin_agente": "sin_agente",
    },
)
_constructor.add_conditional_edges(
    "agentes_remotos",
    _ruta_tras_remotos,
    {"integrador": "integrador", END: END},
)
_constructor.add_edge("pedir_datos", END)
_constructor.add_edge("integrador", END)
_constructor.add_edge("sin_agente", END)
graph = _constructor.compile(checkpointer=MemorySaver())


def _ultimo_texto(estado: dict[str, Any]) -> str:
    for mensaje in reversed(estado.get("messages", [])):
        if isinstance(mensaje, AIMessage):
            return _texto_contenido(mensaje.content)
    return "El supervisor no recibió una respuesta."


async def _asegurar_catalogo() -> None:
    if not _agentes:
        establecer_catalogo(await descubrir())


async def decidir(texto: str) -> dict[str, str]:
    """Devuelve la decisión del supervisor sin invocar al agente elegido."""
    await _asegurar_catalogo()
    cambios = await _nodo_supervisor({"messages": [HumanMessage(content=texto)]})
    return {"agente": cambios["agente"], "motivo": cambios["motivo"]}


async def consultar(texto: str, thread_id: str) -> dict[str, Any]:
    """Consulta al coordinador y devuelve la decisión, respuesta y trazas A2A estructuradas."""
    await _asegurar_catalogo()
    estado = await graph.ainvoke(
        {"messages": [HumanMessage(content=texto)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "agente": estado.get("agente", "ninguno"),
        "motivo": estado.get("motivo", "Sin motivo disponible."),
        "respuesta": estado.get("respuesta") or _ultimo_texto(estado),
        "aportes": estado.get("aportes") or [],
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
                print(f"Agente(s) elegido(s): {cambios.get('agente', 'ninguno')}")
                print(f"Motivo: {cambios.get('motivo', 'sin motivo')}")
            for mensaje in cambios.get("messages", []):
                if isinstance(mensaje, AIMessage):
                    respuesta = _texto_contenido(mensaje.content)
    print(f"Total de saltos: {cantidad}")
    return respuesta


def diagrama() -> None:
    """Imprime el diagrama Mermaid del supervisor."""
    print(graph.get_graph().draw_mermaid())
