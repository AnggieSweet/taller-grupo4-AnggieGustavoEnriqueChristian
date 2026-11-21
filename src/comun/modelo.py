"""obtener_modelo(): Gemini en uso normal, o un modelo de prueba determinista con MODELO=prueba.

El modelo de prueba NO es inteligente: sigue reglas escritas a mano (regex → herramienta).
Sirve para tres cosas: correr los tests sin clave ni internet, que el docente revise el
flujo completo (A2A, ficha, coordinador) sin gastar cuota, y CI. La evidencia del taller
se saca con Gemini, no con este modelo.
"""
from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, ConfigDict

from src import config

# Una regla: (patrón sobre la pregunta, nombre de herramienta, función que arma los argumentos).
Regla = tuple[str, str, Callable[[re.Match, str], dict]]


class ModeloPrueba(BaseChatModel):
    """Modelo determinista: decide herramientas con regex y resume lo que devuelven."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    reglas: list[Regla] = []
    fuera_de_tema: str = "Eso no es de mi especialidad."
    directas: list[tuple[str, str]] = []  # (patrón, respuesta sin herramientas): saludo, nombre
    herramientas: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "modelo-prueba"

    def bind_tools(self, tools: Sequence[Any], **_: Any) -> "ModeloPrueba":
        nombres = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in tools]
        return self.model_copy(update={"herramientas": nombres})

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **_: Any) -> ChatResult:
        ultimo = messages[-1]
        if isinstance(ultimo, ToolMessage):  # ya tengo el dato: respondo con él, sin inventar
            texto = str(ultimo.content).strip()
            mensaje = AIMessage(content=texto[:1200])
        else:
            pregunta = _ultima_pregunta(messages)
            llamada = self._elegir(pregunta)
            directa = next((r for p, r in self.directas if re.search(p, pregunta, flags=re.IGNORECASE)), None)
            if llamada:
                mensaje = AIMessage(content="", tool_calls=[llamada])
            else:
                mensaje = AIMessage(content=directa or self.fuera_de_tema)
        return ChatResult(generations=[ChatGeneration(message=mensaje)])

    def _elegir(self, pregunta: str) -> dict | None:
        for patron, herramienta, argumentos in self.reglas:
            m = re.search(patron, pregunta, flags=re.IGNORECASE | re.DOTALL)
            if m and (not self.herramientas or herramienta in self.herramientas):
                return {"name": herramienta, "args": argumentos(m, pregunta), "id": f"call_{uuid.uuid4().hex[:8]}"}
        return None


def _ultima_pregunta(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


def obtener_modelo(
    temperatura: float = 0.0,
    reglas_prueba: list[Regla] | None = None,
    fuera_de_tema: str = "Eso no es de mi especialidad.",
    directas_prueba: list[tuple[str, str]] | None = None,
) -> BaseChatModel:
    """Gemini (por GOOGLE_API_KEY o Google OAuth/ADC si USAR_OAUTH=true) o el modelo de prueba si MODELO=prueba."""
    if config.modo_prueba():
        return ModeloPrueba(reglas=reglas_prueba or [], fuera_de_tema=fuera_de_tema, directas=directas_prueba or [])
    config.exigir_clave()  # sin clave: una línea clara en vez de un stack trace de pydantic
    from langchain_google_genai import ChatGoogleGenerativeAI

    # gemini-3.5-* usa muestreo fijo y emite un UserWarning si se pasa temperature.
    temp_kwargs = {} if "gemini-3.5" in config.MODELO else {"temperature": temperatura}

    if config.USAR_OAUTH:
        return ChatGoogleGenerativeAI(
            model=config.MODELO,
            vertexai=True,
            project=config.GOOGLE_CLOUD_PROJECT or None,
            location=config.GOOGLE_CLOUD_LOCATION,
            timeout=config.TIMEOUT_A2A,
            max_retries=2,
            **temp_kwargs,
        )

    return ChatGoogleGenerativeAI(
        model=config.MODELO,
        api_key=config.GOOGLE_API_KEY,
        timeout=config.TIMEOUT_A2A,
        max_retries=2,
        **temp_kwargs,
    )


def salida_estructurada(
    esquema: type[BaseModel],
    decidir_prueba: Callable[[str], BaseModel],
    temperatura: float = 0.0,
):
    """with_structured_output(esquema) con Gemini; en modo prueba, una función determinista."""
    if config.modo_prueba():
        def _invocar(entrada: Any) -> BaseModel:
            if isinstance(entrada, list):
                texto = _ultima_pregunta(entrada)
            else:
                texto = str(entrada)
            return decidir_prueba(texto)

        return RunnableLambda(_invocar)
    return obtener_modelo(temperatura).with_structured_output(esquema)


def a_json(valor: Any) -> str:
    """Las herramientas devuelven texto: JSON legible, con tildes, sin errores."""
    return json.dumps(valor, ensure_ascii=False, indent=1)
