"""obtener_modelo() y crear_llm_gemini(): Gemini por GOOGLE_API_KEY o Google OAuth/ADC, o MODELO=prueba."""
from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Callable, Sequence
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, ConfigDict

from src import config

Regla = tuple[str, str, Callable[[re.Match, str], dict]]


class ModeloPrueba(BaseChatModel):
    """Modelo determinista: decide herramientas con regex y resume lo que devuelven."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    reglas: list[Regla] = []
    fuera_de_tema: str = "Eso no es de mi especialidad."
    directas: list[tuple[str, str]] = []
    herramientas: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "modelo-prueba"

    def bind_tools(self, tools: Sequence[Any], **_: Any) -> ModeloPrueba:
        nombres = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in tools]
        return self.model_copy(update={"herramientas": nombres})

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **_: Any) -> ChatResult:
        ultimo = messages[-1]
        if isinstance(ultimo, ToolMessage):
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


def crear_llm_gemini(temperatura: float = 0.0, timeout: float = 30.0, permitir_sin_clave_al_importar: bool = False):
    """Construye ChatGoogleGenerativeAI soportando GOOGLE_API_KEY y USAR_OAUTH=true."""
    load_dotenv()
    from langchain_google_genai import ChatGoogleGenerativeAI

    nombre_modelo = os.environ.get("MODELO", config.MODELO)
    api_key = os.environ.get("GOOGLE_API_KEY", config.GOOGLE_API_KEY).strip()
    usar_oauth = os.environ.get("USAR_OAUTH", "").strip().lower() in ("1", "true", "si", "sí") or config.USAR_OAUTH
    proyecto = os.environ.get("GOOGLE_CLOUD_PROJECT", config.GOOGLE_CLOUD_PROJECT).strip()
    ubicacion = os.environ.get("GOOGLE_CLOUD_LOCATION", config.GOOGLE_CLOUD_LOCATION).strip() or "global"
    temp_kwargs = {} if "gemini-3.5" in nombre_modelo else {"temperature": temperatura}

    if usar_oauth and not api_key:
        creds, proyecto_adc = config.obtener_credenciales_oauth()
        return ChatGoogleGenerativeAI(
            model=nombre_modelo,
            vertexai=True,
            credentials=creds,
            project=proyecto or proyecto_adc or None,
            location=ubicacion,
            timeout=timeout,
            max_retries=2,
            **temp_kwargs,
        )

    if not api_key and not permitir_sin_clave_al_importar:
        config.exigir_clave()

    return ChatGoogleGenerativeAI(
        model=nombre_modelo,
        api_key=api_key or "CLAVE_NO_CONFIGURADA",
        timeout=timeout,
        max_retries=2,
        **temp_kwargs,
    )


def obtener_modelo(
    temperatura: float = 0.0,
    reglas_prueba: list[Regla] | None = None,
    fuera_de_tema: str = "Eso no es de mi especialidad.",
    directas_prueba: list[tuple[str, str]] | None = None,
) -> BaseChatModel:
    """Gemini (por GOOGLE_API_KEY o Google OAuth/ADC si USAR_OAUTH=true) o el modelo de prueba si MODELO=prueba."""
    if config.modo_prueba():
        return ModeloPrueba(reglas=reglas_prueba or [], fuera_de_tema=fuera_de_tema, directas=directas_prueba or [])
    return crear_llm_gemini(temperatura=temperatura, timeout=config.TIMEOUT_A2A, permitir_sin_clave_al_importar=True)


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
