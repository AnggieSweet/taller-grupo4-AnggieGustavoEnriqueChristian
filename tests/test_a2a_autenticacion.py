"""El endpoint A2A de los agentes exige AGENT_API_KEY; la ficha y /salud siguen públicas.

No usan el modelo ni claves reales: el agente responde con una función falsa.
"""
import asyncio

import pytest
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, VERSION_HEADER
from fastapi.testclient import TestClient

from src.comun.servidor import crear_app
from src.comun.tarjeta import crear_tarjeta
from src.coordinador import cliente as cliente_a2a

CLAVE = "clave-agentes-de-prueba"
VERSION = {VERSION_HEADER: PROTOCOL_VERSION_CURRENT}
PETICION = {
    "jsonrpc": "2.0",
    "id": "prueba-1",
    "method": "SendMessage",
    "params": {
        "message": {
            "messageId": "mensaje-prueba-1",
            "role": "ROLE_USER",
            "parts": [{"text": "hola"}],
        }
    },
}


async def _responder_falso(texto: str, context_id: str) -> str:
    return f"eco: {texto}"


def _app():
    tarjeta = crear_tarjeta(
        "Agente de prueba",
        "Agente falso para probar el control de acceso.",
        "http://127.0.0.1:8999",
        [("eco", "Eco", "Repite el texto.", "hola")],
    )
    return crear_app(tarjeta, _responder_falso)


@pytest.fixture
def con_clave(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEY", CLAVE)
    monkeypatch.delenv("URL_PUBLICA", raising=False)
    return TestClient(_app())


def test_ficha_y_salud_son_publicas(con_clave):
    assert con_clave.get("/.well-known/agent-card.json").status_code == 200
    assert con_clave.get("/salud").json() == {"ok": True}


def test_post_a2a_sin_clave_devuelve_401(con_clave):
    r = con_clave.post("/", json=PETICION, headers=VERSION)
    assert r.status_code == 401
    assert "eco" not in r.text


def test_post_a2a_con_clave_incorrecta_devuelve_401(con_clave):
    r = con_clave.post("/", json=PETICION, headers={**VERSION, "X-API-Key": "otra-clave"})
    assert r.status_code == 401


@pytest.mark.parametrize(
    "cabeceras",
    [{"X-API-Key": CLAVE}, {"Authorization": f"Bearer {CLAVE}"}],
    ids=["x-api-key", "bearer"],
)
def test_post_a2a_con_clave_valida_responde(con_clave, cabeceras):
    r = con_clave.post("/", json=PETICION, headers={**VERSION, **cabeceras})
    assert r.status_code == 200
    assert "eco: hola" in r.text


def test_sin_agent_api_key_el_agente_queda_abierto_compatibilidad_local(monkeypatch):
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    r = TestClient(_app()).post("/", json=PETICION, headers=VERSION)
    assert r.status_code == 200
    assert "eco: hola" in r.text


def test_cliente_del_coordinador_envia_la_clave(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEY", CLAVE)
    assert cliente_a2a._cabeceras_a2a()["X-API-Key"] == CLAVE
    monkeypatch.delenv("AGENT_API_KEY")
    assert "X-API-Key" not in cliente_a2a._cabeceras_a2a()


def test_coordinador_conversa_de_punta_a_punta_con_agente_protegido(monkeypatch):
    """El cliente A2A real del coordinador, con la clave, obtiene la respuesta del agente protegido."""
    import httpx

    monkeypatch.setenv("AGENT_API_KEY", CLAVE)
    monkeypatch.delenv("URL_PUBLICA", raising=False)
    app = _app()
    transporte = httpx.ASGITransport(app=app)
    url = "http://127.0.0.1:8999"

    clase_original = httpx.AsyncClient

    def cliente_en_memoria(*args, **kwargs):
        kwargs["transport"] = transporte
        return clase_original(*args, **kwargs)

    monkeypatch.setattr(cliente_a2a.httpx, "AsyncClient", cliente_en_memoria)
    cliente_a2a._CLIENTES.pop(url, None)

    async def flujo():
        cliente = await cliente_a2a.obtener_cliente(url)
        return await cliente_a2a.preguntar(cliente, "hola", "ctx-auth")

    try:
        respuesta = asyncio.run(flujo())
    finally:
        cliente_a2a._CLIENTES.pop(url, None)
        cliente_a2a._HTTP_CLIENTES.pop(url, None)
    assert "eco: hola" in respuesta
