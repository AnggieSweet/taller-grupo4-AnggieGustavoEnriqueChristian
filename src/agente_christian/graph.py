"""Agente de Christian · asistente del Patio de Comidas "Terraza Sabores" (Mall Portal Nativo) · LangGraph.

Molde del agente de viajes (create_agent + herramientas + MemorySaver) envuelto en dos guardrails:

START → guardia_entrada ─┬─ agente (model ⇄ tools) → guardia_salida ─┬─ END
                         │                               ↑  (1 reintento) ┘
                         └─ respuesta_bloqueada → END

El system prompt recibe en cada llamada la fecha, el día, la hora (Santiago) y el canal (middleware dynamic_prompt).
"""
from __future__ import annotations

import asyncio
import logging
import re

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from src import config
from src.agente_christian.prompts import (
    CORRECCION,
    FUERA_DE_TEMA,
    RESPUESTA_NO_CONFIRMADA,
    RESPUESTA_NO_CONFIRMADA_ALERGIA,
    RESPUESTAS_BLOQUEO,
    prompt_con_contexto,
)
from src.agente_christian.tools import CODIGOS_VALIDOS, DIAS, HERRAMIENTAS, PRECIOS_CONOCIDOS, norm
from src.comun.guardias import revisar_entrada, revisar_salida
from src.comun.modelo import obtener_modelo
from src.comun.trazas import imprimir_diagrama, imprimir_saltos, imprimir_saltos_async, ultimo_texto

log = logging.getLogger("agente_christian")

MAX_REINTENTOS = 1
MAX_PALABRAS = 260
# Pedidos que este agente NO hace (además de lo que bloquean las guardias comunes).
# Ojo con los falsos positivos: "¿cómo pido por QR?" o "¿puedo pagar en efectivo?" deben pasar.
ACCIONES_NO_SOPORTADAS = [
    r"\b(hazme|haz|t[oó]mame|toma|ingresa|realiza)\b.{0,15}\b(el|un|mi)?\s*(pedido|orden)\b",
    r"\b(p[ií]deme|p[ií]delo|encarga(me)?|pide\s+por\s+m[ií])\b",
    r"\b(p[aá]game|p[aá]galo|c[oó]brame|c[oó]bralo|cobra\s+a\s+mi|carga(lo)?\s+a\s+mi\s+tarjeta)\b",
    r"\b(puedes|podr[ií]as|quiero\s+que)\s+(pedir|pagar|cobrar|reservar|hacer\s+(el|un|mi)\s+pedido)\b",
    r"\bres[eé]rva(me|nos)?\b.{0,20}\b(mesa|puestos?|lugar)\b",
]
PALABRAS_ALERGIA = r"alerg|al[eé]rgic|cel[ií]ac|intoleran|anafilax|sin gluten|sin lactosa|man[ií]\b"
SEGURIDAD_ABSOLUTA = r"100\s*%\s*segur|totalmente\s+segur|sin\s+ning[uú]n\s+riesgo|libre\s+de\s+riesgo"


class Estado(MessagesState):
    veredicto: str
    categoria: str
    revision: str
    reintentos: int


# ── System prompt con las variables del patio ─────────────────────────────────
@dynamic_prompt
def prompt_del_patio(request: ModelRequest) -> str:
    ahora = config.ahora()
    return prompt_con_contexto(f"{ahora:%d-%m-%Y}", DIAS[ahora.weekday()], f"{ahora:%H:%M}", config.CANAL)


# ── Solo para MODELO=prueba: qué herramienta llamaría un modelo razonable ─────
def _consulta(p: str) -> dict:
    t = norm(p)
    args: dict = {"consulta": p}
    if m := re.search(r"\$?\s?(\d{1,2})[.\s]?(\d{3})\b", p):
        args["presupuesto_max"] = int(m.group(1) + m.group(2))
    for d in ("vegano", "vegetariano", "celiac", "sin gluten", "infantil", "ninos"):
        if d in t:
            args["dieta"] = "sin gluten" if d == "celiac" else d
    if m := re.search(r"alergic[oa] (?:al |a la |a los |a las )?(\w+)|sin (mani|mariscos|lacteos|huevo|soya|sesamo)", t):
        args["sin_alergenos"] = m.group(1) or m.group(2)
    return args


REGLAS_PRUEBA = [
    (r"\bpromo|promoci|descuento|oferta|happy hour", "promociones_vigentes", lambda m, p: {}),
    (r"wifi|wi-fi|ba[ñn]o|mudador|estacion|efectivo|tarjeta|pagar|pago|club nativo|puntos|zona infantil|microondas|"
     r"accesib|reclamo|queja|d[oó]nde queda|qu[eé] piso|horario del patio|a qu[eé] hora (abre|cierra) el patio|mascota|qr|app",
     "info_patio", lambda m, p: {"tema": m.group(0)}),
    (r"comer|qu[eé] como|tengo \$|presupuesto|almorz|cenar|plato|men[uú]|sushi|pizza|hamburgues|burger|helado|caf[eé]|postre|vegan|vegetarian|cel[ií]ac|"
     r"alerg|ceviche|tacos?|completo|poke|shawarma|chilen|peruan|mexican|china|chino|barato|precio|cu[aá]nto (cuesta|vale)|"
     r"recomien|niñ|infantil|coreana|t-\d\d", "buscar_platos", lambda m, p: _consulta(p)),
]

# El agente ReAct (sin checkpointer propio: hereda la memoria del grafo de afuera).
DIRECTAS_PRUEBA = [(r"c[oó]mo te llamas|qui[eé]n eres|tu nombre|hola\b",
                    "Soy Christian, el asistente virtual del patio de comidas Terraza Sabores. ¿Qué se te antoja?")]

agente = create_agent(
    model=obtener_modelo(reglas_prueba=REGLAS_PRUEBA, fuera_de_tema=FUERA_DE_TEMA, directas_prueba=DIRECTAS_PRUEBA),
    tools=HERRAMIENTAS,
    middleware=[prompt_del_patio],
    name="agente",
)


# ── Nodos ─────────────────────────────────────────────────────────────────────
def guardia_entrada(estado: Estado) -> dict:
    texto = str(estado["messages"][-1].content)
    v = revisar_entrada(texto, ACCIONES_NO_SOPORTADAS, config.MAX_LARGO_PREGUNTA)
    if not v.permitido:
        log.info("bloqueo de entrada · categoria=%s · %s", v.categoria, v.motivo)
    return {"veredicto": "permitido" if v.permitido else "bloqueado", "categoria": v.categoria, "reintentos": 0}


def respuesta_bloqueada(estado: Estado) -> dict:
    texto = RESPUESTAS_BLOQUEO[estado["categoria"]].format(max=config.MAX_LARGO_PREGUNTA)
    return {"messages": [AIMessage(texto)]}


def _turno(estado: Estado) -> tuple[str, str]:
    """(pregunta del usuario, texto de las herramientas) del turno actual."""
    mensajes = estado["messages"]
    inicio = max((i for i, m in enumerate(mensajes) if isinstance(m, HumanMessage)
                  and not str(m.content).startswith("[Revisión interna]")), default=0)
    herramientas = " ".join(str(m.content) for m in mensajes[inicio:] if isinstance(m, ToolMessage))
    return str(mensajes[inicio].content), herramientas


def guardia_salida(estado: Estado) -> dict:
    borrador = ultimo_texto({"messages": estado["messages"]})
    pregunta, datos = _turno(estado)
    r = revisar_salida(borrador, MAX_PALABRAS, {c.lower() for c in CODIGOS_VALIDOS}, r"\bT-\d{2}\b")
    problemas, detalles = list(r.problemas), [r.detalle] if r.detalle else []
    # Regla de oro 1: todo monto viene de la carta o de una herramienta de este turno.
    montos = set(re.findall(r"\$\d{1,3}(?:\.\d{3})+|\$\d{3,4}\b", borrador))
    inventados = sorted(m for m in montos if m not in PRECIOS_CONOCIDOS and m not in datos)
    if inventados:
        problemas.append("dato_no_respaldado")
        detalles.append(f"montos sin respaldo en las herramientas: {', '.join(inventados)} (usa calcular_total)")
    # Regla de oro 5: alergias → advertir contaminación cruzada y nunca prometer seguridad total.
    alergia = re.search(PALABRAS_ALERGIA, norm(pregunta))
    if re.search(SEGURIDAD_ABSOLUTA, norm(borrador)):
        problemas.append("seguridad_alimentaria")
        detalles.append("afirma que algo es totalmente seguro")
    if alergia and "contaminacion cruzada" not in norm(borrador):
        problemas.append("seguridad_alimentaria")
        detalles.append("pregunta sobre alergias o dietas sin advertir el riesgo de contaminación cruzada")
    if not problemas:
        return {"revision": "aprobada"}
    log.info("guardia de salida · problemas=%s · %s", problemas, "; ".join(detalles))
    if estado.get("reintentos", 0) < MAX_REINTENTOS:
        return {
            "revision": f"reintento: {', '.join(dict.fromkeys(problemas))}",
            "reintentos": estado.get("reintentos", 0) + 1,
            "messages": [HumanMessage(CORRECCION.format(detalle="; ".join(detalles)))],
        }
    seguro = RESPUESTA_NO_CONFIRMADA_ALERGIA if alergia else RESPUESTA_NO_CONFIRMADA
    return {"revision": f"rechazada: {', '.join(dict.fromkeys(problemas))}", "messages": [AIMessage(seguro)]}


def _tras_entrada(estado: Estado) -> str:
    return "agente" if estado["veredicto"] == "permitido" else "respuesta_bloqueada"


def _tras_salida(estado: Estado) -> str:
    return "agente" if estado.get("revision", "").startswith("reintento") else END


def _construir():
    g = StateGraph(Estado)
    g.add_node("guardia_entrada", guardia_entrada)
    g.add_node("agente", agente)
    g.add_node("guardia_salida", guardia_salida)
    g.add_node("respuesta_bloqueada", respuesta_bloqueada)
    g.add_edge(START, "guardia_entrada")
    g.add_conditional_edges("guardia_entrada", _tras_entrada, ["agente", "respuesta_bloqueada"])
    g.add_edge("agente", "guardia_salida")
    g.add_conditional_edges("guardia_salida", _tras_salida, ["agente", END])
    g.add_edge("respuesta_bloqueada", END)
    return g.compile(checkpointer=MemorySaver(), name="agente_christian")


graph = _construir()


async def responder(texto: str, context_id: str) -> str:
    """Contrato común de todos los agentes: texto + context_id (= thread_id: recuerda la conversación)."""
    resultado = await graph.ainvoke(
        {"messages": [HumanMessage(texto)]},
        {"configurable": {"thread_id": context_id}, "recursion_limit": config.MAX_PASOS_AGENTE * 2},
    )
    return ultimo_texto(resultado)


def saltos(texto: str) -> dict:
    return imprimir_saltos(graph, {"messages": [HumanMessage(texto)]})


async def saltos_async(texto: str) -> dict:
    return await imprimir_saltos_async(graph, {"messages": [HumanMessage(texto)]}, recursion_limit=config.MAX_PASOS_AGENTE * 2)


def diagrama() -> str:
    return imprimir_diagrama(graph)


if __name__ == "__main__":
    print(asyncio.run(responder("¿Qué promos hay hoy?", "demo")))
