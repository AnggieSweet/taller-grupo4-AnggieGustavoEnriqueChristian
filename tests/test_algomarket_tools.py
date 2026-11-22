"""Pruebas deterministas de las herramientas de AlgoMarket (no usan el modelo ni claves)."""
from unittest.mock import patch

from src.agente_algomarket import tools
from src.agente_algomarket.tools import buscar_producto, horario_supermercado


def _buscar(texto):
    return buscar_producto.invoke({"producto": texto})


def _horario(dia):
    return horario_supermercado.invoke({"dia": dia})


def test_producto_exacto_conserva_precio_y_unidad():
    r = _buscar("leche")
    assert r["encontrado"] is True
    assert r["precio_clp"] == 1290
    assert r["unidad"] == "1 litro"
    assert r["oferta"] == "2x1 los martes"


def test_mayusculas_y_plural():
    assert _buscar("  ARROZ ")["producto"] == "arroz"
    assert _buscar("bebida")["producto"] == "bebidas"
    assert _buscar("detergentes")["producto"] == "detergente"


def test_texto_vacio_no_devuelve_un_producto():
    r = _buscar("   ")
    assert r["encontrado"] is False


def test_producto_distinto_no_se_confunde():
    # "aceite de oliva" no es "aceite": se sugiere, no se asume
    r = _buscar("aceite de oliva")
    assert r["encontrado"] is False
    assert r["sugerencias"] == ["aceite"]


def test_producto_inexistente():
    r = _buscar("televisor")
    assert r["encontrado"] is False
    assert r["sugerencias"] == []


def test_oferta_pack_detergente_conserva_condicion():
    r = _buscar("detergente")
    assert r["precio_clp"] == 4590
    assert r["oferta"] == "Pack 2 por $8.000"


def test_horario_con_y_sin_tilde():
    assert _horario("miércoles") == _horario("miercoles")
    r = _horario("domingo")
    assert (r["apertura"], r["cierre"]) == ("10:00", "20:00")


def test_horario_dia_invalido():
    assert _horario("feriado")["encontrado"] is False


def test_horario_hoy_y_manana():
    with patch.object(tools, "_dia_actual", side_effect=lambda d=0: ["martes", "miercoles"][d]):
        assert _horario("hoy")["dia"] == "martes"
        assert _horario("mañana")["dia"] == "miercoles"


def test_comida_de_mascotas_la_atiende_el_supermercado():
    # El supervisor deriva la comida de mascotas a AlgoMarket: el agente debe tener el dato
    for consulta in ["comida para perros", "Alimento para mascotas", "comida para gatos"]:
        r = _buscar(consulta)
        assert r["encontrado"] is True
        assert r["producto"] == "alimento para mascotas"
        assert r["precio_clp"] == 12990


def test_palabra_suelta_sugiere_sin_asumir():
    r = _buscar("alimento")
    assert r["encontrado"] is False
    assert r["sugerencias"] == ["alimento para mascotas"]
