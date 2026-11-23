"""Pruebas deterministas de colaboración multi-agente A2A, fidelidad en CLP y solicitud de datos faltantes."""
import asyncio

from src.comun.guardias import verificar_fidelidad_integracion
from src.coordinador import graph as coord


def test_decision_acepta_multiples_agentes(monkeypatch):
    monkeypatch.setattr(
        coord,
        "_agentes",
        [
            {"nombre": "Agente de Christian", "descripcion": "Patio de comidas"},
            {"nombre": "Agente de Algomarket", "descripcion": "Supermercado"},
        ],
    )
    d = coord.Decision(
        agentes=["Agente de Christian", "Agente de Algomarket"],
        motivo="Combina patio de comidas y supermercado.",
    )
    assert d.agentes == ["Agente de Christian", "Agente de Algomarket"]


def test_verificador_fidelidad_detecta_cifra_alterada():
    reportes = [
        "Pizza sin gluten en Napoli Forno (T-05) a $8.490. Riesgo de contaminación cruzada.",
        "Leche en AlgoMarket cuesta $1.290 por 1 litro (oferta 2x1 los martes).",
    ]
    fiel_ok, inv_ok = verificar_fidelidad_integracion(
        "Puedes comer pizza a $8.490 (riesgo de contaminación cruzada) y comprar leche a $1.290 por 1 litro (total $9.780).",
        reportes,
    )
    assert fiel_ok is True
    assert inv_ok == []

    fiel_mal, inv_mal = verificar_fidelidad_integracion(
        "La pizza cuesta $7.990 y la leche cuesta $1.290.",
        reportes,
    )
    assert fiel_mal is False
    assert 7990 in inv_mal


def test_nodo_pedir_datos_antes_de_concluir():
    salida = coord._nodo_pedir_datos(
        {
            "messages": [],
            "faltan_datos": True,
            "pregunta_aclaracion": "Para cotizar tu estadía, indícame la ciudad de destino y cuántas noches te alojarás.",
        }
    )
    assert "ciudad" in salida["respuesta"]
    assert "noches" in salida["respuesta"]


def test_paralelismo_a2a_conserva_aportes(monkeypatch):
    monkeypatch.setattr(
        coord,
        "_agentes",
        [
            {"nombre": "Agente de Christian", "descripcion": "Patio", "cliente": "c1"},
            {"nombre": "Agente de Algomarket", "descripcion": "Super", "cliente": "c2"},
        ],
    )

    async def preguntar_falso(cliente, texto, context_id):
        if cliente == "c1":
            return "Napoli Forno ofrece pizza sin gluten por $8.490 (riesgo de contaminación cruzada)."
        return "Leche 1 litro a $1.290 en pasillo 3 - Lacteos."

    monkeypatch.setattr(coord, "preguntar", preguntar_falso)

    res = asyncio.run(
        coord._nodo_agentes_remotos(
            {
                "messages": [coord.HumanMessage(content="Pizza sin gluten y precio de la leche")],
                "agentes": ["Agente de Christian", "Agente de Algomarket"],
                "motivo": "Consulta combinada",
            },
            {"configurable": {"thread_id": "t-multi"}},
        )
    )
    assert len(res["aportes"]) == 2
    assert all(a["ok"] for a in res["aportes"])
