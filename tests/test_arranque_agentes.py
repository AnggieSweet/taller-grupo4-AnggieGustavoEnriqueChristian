"""Cada agente A2A debe poder importarse y publicar su ficha.

Evita que un error de importación (p. ej. un merge mal resuelto en graph.py) pase inadvertido:
el resto de las pruebas no importa los servidores, pero todos los scripts de arranque sí.
No usa el modelo ni claves reales.
"""
import importlib
import importlib.util

import pytest
from fastapi.testclient import TestClient

AGENTES = [
    "src.agente_viajes.server",
    "src.agente_anggie.server",
    "src.agente_enrique.server",
    "src.agente_algomarket.server",
    "src.agente_christian.server",
    "src.agente_restaurantes.server",
]


@pytest.mark.parametrize("modulo", AGENTES, ids=lambda m: m.split(".")[1])
def test_agente_importa_y_publica_su_ficha(modulo, monkeypatch):
    if modulo.endswith("agente_restaurantes.server") and importlib.util.find_spec("crewai") is None:
        pytest.skip("CrewAI no está instalado en este entorno (usa .venv-crew / requirements-crew.txt).")
    # CrewAI no reconoce el modelo «prueba»; construir su LLM no llama a la red, así que basta un nombre válido.
    monkeypatch.setenv("MODELO", "gemini-3.5-flash-lite" if "restaurantes" in modulo else "prueba")
    monkeypatch.setenv("GOOGLE_API_KEY", "clave-ficticia-de-prueba")
    monkeypatch.delenv("URL_PUBLICA", raising=False)

    servidor = importlib.import_module(modulo)

    ficha = TestClient(servidor.app).get("/.well-known/agent-card.json")
    assert ficha.status_code == 200
    assert ficha.json()["name"]
