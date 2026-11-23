"""API HTTP del Mall que delega las preguntas al coordinador A2A."""

import asyncio
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from hmac import compare_digest
from typing import Annotated, Any

import httpx
from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Security,
    status,
)
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src import config
from src.comun.guardias import revisar_entrada
from src.coordinador.catalogo import descubrir
from src.coordinador.graph import consultar, establecer_catalogo


load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
_registro = logging.getLogger("api.mall")
MODELO = os.getenv("MODELO", "gemini-3.5-flash-lite")
API_KEY = os.getenv("API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_SECRET = os.getenv("TELEGRAM_SECRET", "")
TELEGRAM_PERMITIDOS = os.getenv("TELEGRAM_PERMITIDOS", "")
TIEMPO_MAXIMO_CONSULTA = 75.0
_catalogo_agentes: list[dict[str, Any]] = []

_MENSAJES_GUARDIA = {
    "inyeccion": "Solicitud rechazada por seguridad: no se permite alterar ni extraer instrucciones internas del sistema.",
    "datos_personales": "Por seguridad, no envíes RUT, números de tarjeta ni contraseñas por este canal.",
    "muy_largo": "El mensaje supera el largo máximo permitido.",
}

_cabecera_api_key = APIKeyHeader(
    name="X-API-Key",
    scheme_name="ApiKeyAuth",
    auto_error=False,
)


class ChatRequest(BaseModel):
    """Pregunta que se enviará al coordinador."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"user_id": "usuario-123", "texto": "¿Qué ofertas hay en cosméticos?"}
            ]
        }
    )

    user_id: str = Field(
        description="Identificador del usuario, usado como thread_id de la conversación.",
        examples=["usuario-123"],
    )
    texto: str = Field(
        min_length=1,
        max_length=2000,
        description="Pregunta que el coordinador derivará al agente o agentes adecuados.",
        examples=["¿Qué ofertas hay en cosméticos?"],
    )

    @field_validator("texto")
    @classmethod
    def validar_texto_no_vacio(cls, texto: str) -> str:
        if not texto.strip():
            raise ValueError("El texto no puede estar vacío ni contener solo espacios.")
        return texto


class ChatResponse(BaseModel):
    """Decisión del coordinador y respuesta obtenida."""

    agente: str = Field(
        description="Nombre del agente (o agentes separados por ' + ') elegidos por el coordinador.",
        examples=["Agente de Anggie"],
    )
    motivo: str = Field(
        description="Motivo de enrutamiento indicado por el supervisor.",
        examples=["La pregunta trata sobre ofertas en cosméticos."],
    )
    respuesta: str = Field(
        description="Respuesta integrada conservando cifras, unidades y condiciones.",
        examples=["Hay ofertas disponibles en cosméticos."],
    )


class AgenteResponse(BaseModel):
    """Resumen público de un agente disponible."""

    nombre: str = Field(description="Nombre exacto de la ficha del agente.", examples=["Agente de Anggie"])
    descripcion: str = Field(
        description="Descripción de las capacidades del agente.",
        examples=["Información sobre tiendas y productos del mall."],
    )


class HealthResponse(BaseModel):
    ok: bool
    modelo: str


def _secretos_configurados() -> list[str]:
    return [
        valor
        for nombre, valor in os.environ.items()
        if valor and any(parte in nombre.upper() for parte in ("KEY", "TOKEN", "SECRET"))
    ]


def _limpiar_detalle(detalle: str) -> str:
    """Quita claves y tokens conocidos de cualquier texto destinado al log."""
    return _redactar_secretos(" ".join(detalle.splitlines()).strip())


def _redactar_secretos(texto: str) -> str:
    """Redacta credenciales conocidas preservando el formato del texto."""
    limpio = texto
    for secreto in _secretos_configurados():
        limpio = limpio.replace(secreto, "[REDACTADO]")
    return limpio


_PREFIJOS_FALLO_AGENTE = (
    "no se pudo contactar al agente:",
    "no se pudo procesar el mensaje:",
    "error al procesar la recomendación:",
)


def _es_fallo_de_agente(texto: str) -> bool:
    """Indica si el texto es un mensaje de falla de un agente y no una respuesta."""
    return texto.strip().lower().startswith(_PREFIJOS_FALLO_AGENTE)


def _contiene_traza(texto: str) -> bool:
    return bool(
        re.search(r"Traceback \(most recent call last\):|^\s+File \".+\", line \d+", texto, re.MULTILINE)
    )


def _urls_configuradas() -> set[str]:
    urls = [
        os.getenv("URL_VIAJES", ""),
        os.getenv("URL_RESTAURANTES", ""),
        *os.getenv("URLS_AGENTES", "").split(","),
    ]
    return {url.strip().rstrip("/") for url in urls if url.strip()}


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Carga una vez el catálogo y lo comparte con el coordinador."""
    global _catalogo_agentes
    try:
        _catalogo_agentes = await descubrir()
        establecer_catalogo(_catalogo_agentes)
        if len(_catalogo_agentes) < len(_urls_configuradas()):
            _registro.warning("Algunos agentes no respondieron al cargar el catálogo; se continúa con los disponibles.")
        _registro.info("Catálogo A2A cargado: %s agente(s).", len(_catalogo_agentes))
    except Exception as error:
        _catalogo_agentes = []
        establecer_catalogo([])
        _registro.error("No se pudo cargar el catálogo: %s", _limpiar_detalle(str(error)))
    yield


app = FastAPI(
    title="API del Mall · Taller A2A",
    version="1.0.0",
    description=(
        "La API recibe preguntas autenticadas y el coordinador las deriva o integra por A2A "
        "entre los agentes especialistas (tiendas, cine, supermercado, patio de comidas, viajes y restaurantes)."
    ),
    openapi_tags=[
        {"name": "salud", "description": "Estado de la API."},
        {"name": "agentes", "description": "Agentes disponibles en el catálogo A2A."},
        {"name": "chat", "description": "Consultas conversacionales al coordinador."},
    ],
    lifespan=lifespan,
)


async def validar_api_key(
    api_key: Annotated[str | None, Security(_cabecera_api_key)],
) -> None:
    if not api_key or not API_KEY or not compare_digest(api_key, API_KEY):
        motivo = "sin_clave" if not api_key else "clave_invalida"
        _registro.warning("Control de acceso rechazado (401) · motivo=%s", motivo)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acceso no autorizado",
        )


@app.get("/health", response_model=HealthResponse, tags=["salud"])
async def health() -> HealthResponse:
    """Comprueba que la API está activa y muestra el modelo configurado."""
    return HealthResponse(ok=True, modelo=MODELO)


@app.get(
    "/agentes",
    response_model=list[AgenteResponse],
    tags=["agentes"],
    dependencies=[Depends(validar_api_key)],
    responses={401: {"description": "Acceso no autorizado."}},
)
async def listar_agentes() -> list[AgenteResponse]:
    """Devuelve los nombres y descripciones del catálogo cargado al iniciar."""
    return [
        AgenteResponse(
            nombre=agente["nombre"],
            descripcion=agente.get("descripcion") or "",
        )
        for agente in _catalogo_agentes
    ]


@app.post(
    "/chat",
    response_model=ChatResponse,
    tags=["chat"],
    dependencies=[Depends(validar_api_key)],
    responses={
        200: {"description": "Decisión y respuesta del coordinador."},
        400: {"description": "Entrada bloqueada por seguridad (inyección o datos personales)."},
        401: {"description": "Acceso no autorizado."},
        422: {"description": "El cuerpo o el texto de la pregunta no es válido."},
        502: {"description": "El modelo o un agente no pudo responder."},
        504: {"description": "Se agotó el tiempo de espera."},
    },
)
async def chat(peticion: ChatRequest) -> ChatResponse:
    """Pasa la pregunta al coordinador usando user_id como thread_id."""
    req_id = f"req_{secrets.token_hex(4)}"
    veredicto = revisar_entrada(peticion.texto, [], config.MAX_LARGO_PREGUNTA)
    if not veredicto.permitido:
        _registro.warning(
            "Entrada bloqueada · req_id=%s · user_id=%s · categoria=%s",
            req_id,
            peticion.user_id,
            veredicto.categoria,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_MENSAJES_GUARDIA.get(veredicto.categoria, "Entrada rechazada por validación de seguridad."),
        )

    if not _catalogo_agentes:
        _registro.error("No hay agentes disponibles en el catálogo cargado al iniciar la API.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No hay agentes disponibles para procesar la pregunta.",
        )

    t0 = time.perf_counter()
    try:
        async with asyncio.timeout(TIEMPO_MAXIMO_CONSULTA):
            resultado = await consultar(peticion.texto, thread_id=peticion.user_id)
    except TimeoutError as error:
        _registro.error("Tiempo de espera agotado · req_id=%s · detalle=%s", req_id, _limpiar_detalle(str(error)))
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Se agotó el tiempo de espera al procesar la pregunta.",
        ) from None
    except Exception as error:
        _registro.error("Error del coordinador · req_id=%s · detalle=%s", req_id, _limpiar_detalle(str(error)))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo obtener una respuesta del coordinador.",
        ) from None

    respuesta = str(resultado.get("respuesta", ""))
    detalle_fallo = _limpiar_detalle(respuesta)
    if _es_fallo_de_agente(detalle_fallo):
        _registro.error("Fallo del agente remoto · req_id=%s · detalle=%s", req_id, detalle_fallo)
        if any(termino in detalle_fallo.casefold() for termino in ("tiempo de espera", "timeout", "timed out")):
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Se agotó el tiempo de espera al consultar el agente.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo obtener una respuesta del agente.",
        )
    if any(_contiene_traza(str(resultado.get(campo, ""))) for campo in ("respuesta", "motivo", "agente")):
        _registro.error("El coordinador devolvió una traza de error · req_id=%s", req_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo obtener una respuesta del coordinador.",
        )

    latencia_ms = round((time.perf_counter() - t0) * 1000)
    resumen_a2a = ", ".join(
        f"{a['nombre']}({a['latencia_ms']}ms)"
        for a in (resultado.get("aportes") or [])
        if isinstance(a, dict) and "nombre" in a
    ) or "sin_llamada_remota"
    _registro.info(
        "Consulta completada · req_id=%s · user_id=%s · decision=%s · a2a=[%s] · total=%sms",
        req_id,
        peticion.user_id,
        resultado.get("agente", "ninguno"),
        resumen_a2a,
        latencia_ms,
    )

    valores_limpios = {
        campo: _redactar_secretos(str(resultado.get(campo, "")))
        for campo in ("agente", "motivo", "respuesta")
    }
    return ChatResponse(**valores_limpios)


async def _enviar_mensaje_telegram(chat_id: str, texto: str) -> None:
    """Envía una respuesta al chat, sin registrar la URL que contiene el token."""
    if not TELEGRAM_TOKEN:
        _registro.error("No se puede enviar el mensaje: TELEGRAM_TOKEN no está configurado.")
        return
    texto = texto.replace("**", "")
    if TELEGRAM_TOKEN in texto:
        texto = texto.replace(TELEGRAM_TOKEN, "[REDACTADO]")
    try:
        async with httpx.AsyncClient(timeout=30.0) as cliente:
            respuesta = await cliente.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": texto[:4000]},
            )
            respuesta.raise_for_status()
    except Exception as error:
        _registro.error("No se pudo enviar el mensaje de Telegram (%s).", type(error).__name__)


def _enmascarar_chat_id(chat_id: str) -> str:
    if len(chat_id) <= 4:
        return "***"
    return f"***{chat_id[-4:]}"


async def _procesar_actualizacion_telegram(actualizacion: Any) -> None:
    """Valida el chat, consulta al coordinador si está permitido y responde."""
    req_id = f"tg_{secrets.token_hex(4)}"
    try:
        mensaje = actualizacion.get("message") if isinstance(actualizacion, dict) else None
        chat = mensaje.get("chat") if isinstance(mensaje, dict) else None
        chat_id_original = chat.get("id") if isinstance(chat, dict) else None
        if chat_id_original is None:
            _registro.warning("Actualización de Telegram sin message.chat.id; no se puede responder.")
            return
        chat_id = str(chat_id_original)

        texto = mensaje.get("text")
        if not isinstance(texto, str) or not texto.strip():
            await _enviar_mensaje_telegram(chat_id, "Solo entiendo mensajes de texto")
            return

        permitidos = {valor.strip() for valor in TELEGRAM_PERMITIDOS.split(",") if valor.strip()}
        if chat_id not in permitidos:
            _registro.warning(
                "Telegram acceso rechazado · req_id=%s · chat=%s (no está en TELEGRAM_PERMITIDOS)",
                req_id,
                _enmascarar_chat_id(chat_id),
            )
            await _enviar_mensaje_telegram(chat_id, f"No autorizado. Tu chat_id es {chat_id}")
            return

        veredicto = revisar_entrada(texto, [], config.MAX_LARGO_PREGUNTA)
        if not veredicto.permitido:
            _registro.warning(
                "Telegram entrada bloqueada · req_id=%s · chat=%s · categoria=%s",
                req_id,
                _enmascarar_chat_id(chat_id),
                veredicto.categoria,
            )
            await _enviar_mensaje_telegram(
                chat_id,
                _MENSAJES_GUARDIA.get(veredicto.categoria, "Solicitud rechazada por validación de seguridad."),
            )
            return

        t0 = time.perf_counter()
        try:
            async with asyncio.timeout(TIEMPO_MAXIMO_CONSULTA):
                resultado = await consultar(texto, thread_id=f"tg-{chat_id}")
        except Exception as error:
            _registro.error(
                "Falló la consulta del coordinador desde Telegram · req_id=%s · tipo=%s",
                req_id,
                type(error).__name__,
            )
            await _enviar_mensaje_telegram(chat_id, "Hubo un problema al consultar el servicio, intenta de nuevo.")
            return

        respuesta = str(resultado.get("respuesta", ""))
        if not respuesta or _es_fallo_de_agente(respuesta):
            tipo_error = "RespuestaVacia"
            if _es_fallo_de_agente(respuesta):
                tipo_error = (
                    "TimeoutError"
                    if any(palabra in respuesta.casefold() for palabra in ("tiempo de espera", "timeout", "timed out"))
                    else "ErrorAgenteRemoto"
                )
            _registro.error(
                "Falló el agente desde Telegram · req_id=%s · tipo=%s · agente=%s",
                req_id,
                tipo_error,
                resultado.get("agente") or "no disponible",
            )
            respuesta = "Hubo un problema al consultar al agente especialista, intenta de nuevo."
        else:
            latencia_ms = round((time.perf_counter() - t0) * 1000)
            resumen_a2a = ", ".join(
                f"{a['nombre']}({a['latencia_ms']}ms)"
                for a in (resultado.get("aportes") or [])
                if isinstance(a, dict) and "nombre" in a
            ) or "sin_llamada_remota"
            _registro.info(
                "Telegram consulta completada · req_id=%s · chat=%s · decision=%s · a2a=[%s] · total=%sms",
                req_id,
                _enmascarar_chat_id(chat_id),
                resultado.get("agente", "ninguno"),
                resumen_a2a,
                latencia_ms,
            )

        if TELEGRAM_TOKEN:
            respuesta = respuesta.replace(TELEGRAM_TOKEN, "[REDACTADO]")
        await _enviar_mensaje_telegram(chat_id, respuesta)
    except Exception as error:
        _registro.error("Error procesando la actualización de Telegram (%s).", type(error).__name__)


@app.post("/telegram", include_in_schema=False)
async def telegram(
    tareas: BackgroundTasks,
    actualizacion: Any = Body(...),
    secreto: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict[str, bool]:
    """Valida el webhook y delega su trabajo a una tarea en segundo plano."""
    if not secreto or not TELEGRAM_SECRET or not compare_digest(secreto, TELEGRAM_SECRET):
        _registro.warning("Webhook /telegram rechazado (401) · secreto ausente o inválido")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acceso no autorizado",
        )
    tareas.add_task(_procesar_actualizacion_telegram, actualizacion)
    return {"ok": True}
