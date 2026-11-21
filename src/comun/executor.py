"""Adaptador compartido entre un agente y el protocolo A2A."""

import inspect
from collections.abc import Awaitable, Callable
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue_v2 import EventQueue
from a2a.types import Message, Part, Role


class Executor(AgentExecutor):
    """Envía cada mensaje entrante a la función responder del agente."""

    def __init__(
        self,
        responder: Callable[[str, str], str | Awaitable[str]],
    ) -> None:
        self.responder = responder

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        texto = context.get_user_input()
        context_id = context.context_id or str(uuid4())

        try:
            respuesta = self.responder(texto, context_id)
            if inspect.isawaitable(respuesta):
                respuesta = await respuesta
            texto_respuesta = str(respuesta)
        except Exception as error:
            detalle = " ".join(str(error).splitlines()).strip()
            texto_respuesta = f"No se pudo procesar el mensaje: {detalle or 'error inesperado'}."

        await event_queue.enqueue_event(
            Message(
                message_id=str(uuid4()),
                context_id=context_id,
                role=Role.ROLE_AGENT,
                parts=[Part(text=texto_respuesta)],
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        context_id = context.context_id or str(uuid4())
        await event_queue.enqueue_event(
            Message(
                message_id=str(uuid4()),
                context_id=context_id,
                role=Role.ROLE_AGENT,
                parts=[Part(text="La cancelación no está soportada.")],
            )
        )
