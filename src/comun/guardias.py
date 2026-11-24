"""Guardrails deterministas (regex): primero lo obvio, gratis y sin modelo (clase MCP y guardrails).

Se usan como nodos del grafo y filtro de entrada de la API: guardia_entrada, guardia_salida
y verificador de fidelidad numérica en CLP para respuestas multi-agente.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

INYECCION = [
    r"\b(ignora|olvida|omite|salta(te)?)\b.{0,40}\b(instrucciones|reglas|indicaciones|prompt|restricciones)\b",
    r"\b(ignore|forget|disregard)\b.{0,30}\b(instructions|rules|prompt)\b",
    r"\b(system\s*prompt|prompt\s+del\s+sistema|tus\s+instrucciones\s+(internas|originales))\b",
    r"\b(ahora\s+eres|act[uú]a\s+como|finge\s+que\s+eres|modo\s+(dan|desarrollador|developer))\b",
    r"\b(revela|mu[eé]strame|dime|imprime)\b.{0,30}\b(tu|tus)\s+(prompt|instrucciones|reglas)\b",
]
DATOS_PERSONALES = [
    r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b",       # RUT chileno
    r"\b(?:\d[ -]?){13,16}\b",                    # tarjeta
    r"\b(mi|su)\s+(rut|c[eé]dula|tarjeta|clave|contrase[ñn]a)\s+(es|:)",
]
SECRETOS_SALIDA = [
    r"AIza[0-9A-Za-z_\-]{20,}",                   # clave de Google
    r"\b(password|contrase[ñn]a|api[_ ]?key|token)\s*[:=]\s*\S{6,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
]
PATRON_MONTO_CLP = re.compile(r"\$\s?\d{1,3}(?:\.\d{3})+|\$\s?\d{3,6}\b")


@dataclass
class Veredicto:
    permitido: bool
    categoria: str = "ok"
    motivo: str = ""


@dataclass
class Revision:
    aprobada: bool
    problemas: list[str] = field(default_factory=list)
    detalle: str = ""


def _busca(patrones: list[str], texto: str) -> str | None:
    for p in patrones:
        m = re.search(p, texto, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(0)[:60]
    return None


def revisar_entrada(texto: str, acciones_no_soportadas: list[str], max_largo: int) -> Veredicto:
    """¿Se atiende este mensaje? Inyección, datos personales, acción no soportada o demasiado largo."""
    if len(texto) > max_largo:
        return Veredicto(False, "muy_largo", f"{len(texto)} caracteres")
    if hit := _busca(INYECCION, texto):
        return Veredicto(False, "inyeccion", f"patrón: {hit!r}")
    if hit := _busca(DATOS_PERSONALES, texto):
        return Veredicto(False, "datos_personales", "contiene un dato personal")
    if hit := _busca(acciones_no_soportadas, texto):
        return Veredicto(False, "accion_no_soportada", f"patrón: {hit!r}")
    return Veredicto(True, "ok", "")


def revisar_salida(texto: str, max_palabras: int, nombres_validos: set[str], patron_nombres: str | None) -> Revision:
    """¿Se puede decir esto? Secretos, datos personales, nombres no respaldados y largo."""
    problemas, detalles = [], []
    if _busca(SECRETOS_SALIDA, texto):
        problemas.append("secreto")
        detalles.append("incluye algo con forma de clave o contraseña")
    if _busca(DATOS_PERSONALES[:2], texto):
        problemas.append("datos_personales")
        detalles.append("incluye un RUT o número de tarjeta")
    if patron_nombres:
        inventados = sorted({n.lower() for n in re.findall(patron_nombres, texto)} - nombres_validos)
        if inventados:
            problemas.append("dato_no_respaldado")
            detalles.append(f"menciona nombres que no están en los datos: {', '.join(inventados)}")
    sin_codigo = re.sub(r"```.*?```", " ", texto, flags=re.S)
    if len(sin_codigo.split()) > max_palabras:
        problemas.append("formato")
        detalles.append(f"supera {max_palabras} palabras fuera del código")
    return Revision(not problemas, problemas, "; ".join(detalles))


def extraer_montos_enteros(texto: str) -> set[int]:
    """Normaliza montos en CLP (ej. '$1.290' o '$ 36.792' -> 1290, 36792)."""
    montos: set[int] = set()
    for m in PATRON_MONTO_CLP.findall(texto):
        digitos = re.sub(r"\D", "", m)
        if digitos:
            montos.add(int(digitos))
    return montos


def verificar_fidelidad_integracion(texto_integrado: str, reportes_fuente: list[str]) -> tuple[bool, list[int]]:
    """Comprueba que la conclusión integrada no altere ni invente cifras en CLP respecto de los reportes A2A.

    Acepta montos presentes literalmente en cualquiera de los reportes de los agentes especialistas
    o sumas exactas directas de dichos montos cuando el usuario pidió un total combinado.
    """
    fuente_unida = "\n".join(reportes_fuente)
    montos_fuente = extraer_montos_enteros(fuente_unida)
    # También considera números enteros >= 100 que un agente haya escrito como '1290 CLP' sin signo '$'
    for num in re.findall(r"\b\d{1,3}(?:\.\d{3})+\b|\b\d{3,6}\b", fuente_unida):
        limpio = re.sub(r"\D", "", num)
        if limpio:
            montos_fuente.add(int(limpio))

    montos_salida = extraer_montos_enteros(texto_integrado)
    if not montos_salida:
        return True, []

    sumas_validas = set(montos_fuente)
    lista_fuente = sorted(montos_fuente)
    if len(lista_fuente) >= 2:
        sumas_validas.add(sum(lista_fuente))
        for i, a in enumerate(lista_fuente):
            for b in lista_fuente[i + 1 :]:
                sumas_validas.add(a + b)

    no_respaldados = sorted(m for m in montos_salida if m not in sumas_validas)
    return len(no_respaldados) == 0, no_respaldados
