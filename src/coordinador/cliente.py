"""Cliente A2A compartido para comunicarse con agentes remotos."""

import asyncio
from uuid import uuid4

import httpx

from a2a.client import A2ACardResolver, Client, ClientCallContext, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    GetTaskRequest,
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    Task,
    TaskState,
)
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, VERSION_HEADER


TIMEOUT_RED = 15.0
TIMEOUT_PREGUNTA = 60.0
_CLIENTES: dict[str, Client] = {}
_HTTP_CLIENTES: dict[str, httpx.AsyncClient] = {}
FICHAS_POR_URL: dict[str, AgentCard] = {}


async def obtener_cliente(url: str) -> Client:
    """Resuelve y cachea la ficha y el cliente A2A de una URL."""
    url_normalizada = url.strip().rstrip("/")
    if url_normalizada in _CLIENTES:
        return _CLIENTES[url_normalizada]

    http_cliente = httpx.AsyncClient(
        timeout=TIMEOUT_RED,
        headers={VERSION_HEADER: PROTOCOL_VERSION_CURRENT},
    )
    try:
        resolver = A2ACardResolver(http_cliente, url_normalizada)
        tarjeta = await resolver.get_agent_card()
        configuracion = ClientConfig(
            streaming=False,
            polling=False,
            supported_protocol_bindings=["JSONRPC"],
            httpx_client=http_cliente,
        )
        cliente = ClientFactory(configuracion).create(tarjeta)
    except Exception:
        await http_cliente.aclose()
        raise

    _CLIENTES[url_normalizada] = cliente
    _HTTP_CLIENTES[url_normalizada] = http_cliente
    FICHAS_POR_URL[url_normalizada] = tarjeta
    return cliente


def _texto_partes(partes) -> str:
    return "\n".join(parte.text for parte in partes if getattr(parte, "text", "")).strip()


def _texto_tarea(tarea: Task) -> str:
    textos = [
        _texto_partes(artefacto.parts)
        for artefacto in tarea.artifacts
        if artefacto.parts
    ]
    if tarea.status.HasField("message"):
        texto_estado = _texto_partes(tarea.status.message.parts)
        if texto_estado:
            textos.append(texto_estado)
    return "\n".join(texto for texto in textos if texto).strip()


async def _esperar_tarea(cliente: Client, tarea: Task) -> str:
    estados_finales = {
        TaskState.TASK_STATE_COMPLETED,
        TaskState.TASK_STATE_FAILED,
        TaskState.TASK_STATE_CANCELED,
        TaskState.TASK_STATE_REJECTED,
        TaskState.TASK_STATE_INPUT_REQUIRED,
        TaskState.TASK_STATE_AUTH_REQUIRED,
    }
    while tarea.status.state not in estados_finales:
        await asyncio.sleep(0.5)
        tarea = await cliente.get_task(
            GetTaskRequest(id=tarea.id),
            context=ClientCallContext(timeout=TIMEOUT_RED),
        )
    return _texto_tarea(tarea)


async def preguntar(cliente: Client, texto: str, context_id: str) -> str:
    """Envía un mensaje A2A y obtiene texto directo o el resultado de una tarea."""
    mensaje = Message(
        message_id=str(uuid4()),
        context_id=context_id,
        role=Role.ROLE_USER,
        parts=[Part(text=texto)],
    )
    peticion = SendMessageRequest(
        message=mensaje,
        configuration=SendMessageConfiguration(
            accepted_output_modes=["text/plain"],
        ),
    )
    try:
        async with asyncio.timeout(TIMEOUT_PREGUNTA):
            async for evento in cliente.send_message(
                peticion,
                context=ClientCallContext(timeout=TIMEOUT_RED),
            ):
                if evento.HasField("message"):
                    return _texto_partes(evento.message.parts)
                if evento.HasField("task"):
                    return await _esperar_tarea(cliente, evento.task)
        return "El agente remoto no devolvió una respuesta."
    except TimeoutError as error:
        raise TimeoutError("Se agotó el tiempo de espera al consultar el agente remoto") from error
