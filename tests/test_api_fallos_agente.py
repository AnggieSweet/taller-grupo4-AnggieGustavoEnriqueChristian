"""Las fallas de un agente no deben presentarse como una respuesta exitosa (200).

No usan el modelo ni claves: se reemplaza `consultar` por una función falsa.
"""
import pytest
from fastapi.testclient import TestClient

import api.app as app_mod

CLAVE = "clave-de-prueba"
CABECERAS = {"X-API-Key": CLAVE}
PETICION = {"user_id": "usuario-prueba", "texto": "¿Cuánto cuesta la leche?"}


def _cliente(monkeypatch, respuesta: str) -> TestClient:
    async def consultar_falso(texto, thread_id):
        return {"agente": "Agente de Gustavo", "motivo": "prueba", "respuesta": respuesta}

    monkeypatch.setattr(app_mod, "consultar", consultar_falso)
    monkeypatch.setattr(app_mod, "_catalogo_agentes", [{"nombre": "Agente de Gustavo", "descripcion": "prueba"}])
    monkeypatch.setattr(app_mod, "API_KEY", CLAVE)
    return TestClient(app_mod.app)


def test_respuesta_normal_devuelve_200(monkeypatch):
    r = _cliente(monkeypatch, "La leche cuesta $1.290 por 1 litro.").post("/chat", json=PETICION, headers=CABECERAS)
    assert r.status_code == 200
    assert "1.290" in r.json()["respuesta"]


@pytest.mark.parametrize(
    "texto_de_falla",
    [
        "No se pudo procesar el mensaje: 503 UNAVAILABLE",
        "no se pudo procesar el mensaje: error inesperado.",
    ],
)
def test_falla_del_modelo_dentro_del_agente_devuelve_502(monkeypatch, texto_de_falla):
    r = _cliente(monkeypatch, texto_de_falla).post("/chat", json=PETICION, headers=CABECERAS)
    assert r.status_code == 502
    assert "503" not in r.text  # no se filtra el detalle interno al cliente


def test_agente_remoto_caido_devuelve_502(monkeypatch):
    r = _cliente(monkeypatch, "No se pudo contactar al agente: conexión rechazada.").post(
        "/chat", json=PETICION, headers=CABECERAS
    )
    assert r.status_code == 502


def test_agente_lento_devuelve_504(monkeypatch):
    r = _cliente(monkeypatch, "No se pudo contactar al agente: tiempo de espera agotado.").post(
        "/chat", json=PETICION, headers=CABECERAS
    )
    assert r.status_code == 504


def test_sin_clave_devuelve_401(monkeypatch):
    assert _cliente(monkeypatch, "hola").post("/chat", json=PETICION).status_code == 401


def test_texto_vacio_devuelve_422(monkeypatch):
    r = _cliente(monkeypatch, "hola").post("/chat", json={"user_id": "u", "texto": "   "}, headers=CABECERAS)
    assert r.status_code == 422
