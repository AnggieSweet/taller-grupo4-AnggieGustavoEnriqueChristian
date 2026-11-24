"""La respuesta del agente debe ser texto plano, sin la estructura interna del modelo."""
from src.agente_algomarket.texto import texto_de_contenido


def test_texto_simple_queda_igual():
    assert texto_de_contenido("La leche cuesta $1.290 CLP por 1 litro.") == "La leche cuesta $1.290 CLP por 1 litro."


def test_bloques_del_modelo_se_convierten_en_texto():
    contenido = [
        {
            "type": "text",
            "text": "La leche cuesta $1.290 CLP por 1 litro y está en el pasillo 3 - Lácteos.",
            "extras": {"signature": "Eo4BCosBAWkUfRPtDkj100XxduZK8x=="},
        }
    ]
    resultado = texto_de_contenido(contenido)
    assert resultado == "La leche cuesta $1.290 CLP por 1 litro y está en el pasillo 3 - Lácteos."
    assert "signature" not in resultado and "extras" not in resultado


def test_varios_bloques_se_unen():
    contenido = [{"type": "text", "text": "Primera línea."}, {"type": "text", "text": "Segunda línea."}]
    assert texto_de_contenido(contenido) == "Primera línea.\nSegunda línea."


def test_cifras_y_unidades_no_se_alteran():
    contenido = [{"type": "text", "text": "Pack 2 por $8.000 (precio unitario $4.590, 1 botella)."}]
    resultado = texto_de_contenido(contenido)
    for dato in ("$8.000", "$4.590", "1 botella"):
        assert dato in resultado


def test_vacio_y_none():
    assert texto_de_contenido(None) == ""
    assert texto_de_contenido([]) == ""
