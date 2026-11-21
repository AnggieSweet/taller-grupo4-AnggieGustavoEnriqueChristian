"""Creación de fichas públicas de agentes A2A."""

from collections.abc import Iterable
import os

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from dotenv import load_dotenv


def crear_tarjeta(
    nombre: str,
    descripcion: str,
    url: str,
    skills: Iterable[tuple[str, str, str, str]],
    tags: Iterable[str] | None = None,
) -> AgentCard:
    """Construye una ficha A2A con habilidades y modos de texto."""
    load_dotenv()
    url_publica = os.getenv("URL_PUBLICA", "").strip()
    if url_publica:
        url = url_publica

    etiquetas_generales = list(tags or [])
    habilidades = [
        AgentSkill(
            id=identificador,
            name=nombre_habilidad,
            description=descripcion_habilidad,
            tags=(
                list(dict.fromkeys([*etiquetas_generales, nombre_habilidad]))
                if etiquetas_generales
                else [nombre_habilidad]
            ),
            examples=[ejemplo],
            input_modes=["text/plain"],
            output_modes=["text/plain"],
        )
        for identificador, nombre_habilidad, descripcion_habilidad, ejemplo in skills
    ]

    return AgentCard(
        name=nombre,
        description=descripcion,
        supported_interfaces=[
            AgentInterface(
                url=url,
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=habilidades,
    )
