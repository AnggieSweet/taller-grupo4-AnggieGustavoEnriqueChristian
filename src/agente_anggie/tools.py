"""Herramientas de consulta del mall y sus cuatro tiendas."""

import re
import unicodedata

from langchain_core.tools import tool


_MALL = {
    "calzado": {
        "tienda": "Calzado Paso Firme",
        "local": 124,
        "piso": 1,
        "productos": [
            {
                "nombre": "Zapato de mujer Aurora",
                "tipo": "zapato de mujer",
                "palabras_clave": "zapato calzado zapatilla mujer dama",
                "precio_normal": 45990,
                "stock": 6,
                "tallas": [36, 37, 38, 39, 40],
                "oferta": {"precio": 36792, "descuento": 20, "termina": "30 de noviembre de 2026"},
            },
            {
                "nombre": "Zapato de hombre Urbano",
                "tipo": "zapato de hombre",
                "palabras_clave": "zapato calzado zapatilla hombre caballero",
                "precio_normal": 58990,
                "stock": 4,
                "tallas": [39, 40, 41, 42, 43],
                "oferta": {"precio": 53091, "descuento": 10, "termina": "30 de noviembre de 2026"},
            },
            {
                "nombre": "Zapato unisex Andino",
                "tipo": "zapato unisex",
                "palabras_clave": "zapato calzado zapatilla unisex",
                "precio_normal": 39990,
                "stock": 0,
                "tallas": [37, 38, 39, 40, 41],
                "oferta": None,
            },
        ],
    },
    "cosmetica": {
        "tienda": "Cosmética Brillo Natural",
        "local": 208,
        "piso": 2,
        "productos": [
            {
                "nombre": "Labial Color Vivo",
                "tipo": "labial",
                "palabras_clave": "labial pintalabios lipstick labios maquillaje",
                "precio_normal": 9990,
                "stock": 8,
                "tonos": ["Rosa", "Coral", "Rojo", "Nude"],
                "oferta": {"precio": 7992, "descuento": 20, "termina": "30 de noviembre de 2026"},
            },
            {
                "nombre": "Rubor Luz de Rosa",
                "tipo": "rubor",
                "palabras_clave": "rubor colorete blush maquillaje",
                "precio_normal": 8990,
                "stock": 5,
                "tonos": ["Durazno", "Rosa", "Terracota"],
                "oferta": {"precio": 6293, "descuento": 30, "termina": "30 de noviembre de 2026"},
            },
            {
                "nombre": "Máscara de pestañas Definición",
                "tipo": "máscara de pestañas",
                "palabras_clave": "mascara pestañas rimel rímel maquillaje",
                "precio_normal": 12990,
                "stock": 7,
                "tonos": ["Negro", "Café"],
                "oferta": None,
            },
        ],
    },
    "mascotas": {
        "tienda": "Mascotas Huella Feliz",
        "local": 316,
        "piso": 2,
        "productos": [
            {
                "nombre": "Collar Resistente Huella",
                "tipo": "collar para mascota",
                "palabras_clave": "collar mascota identificacion",
                "precio_normal": 9990,
                "stock": 9,
                "tallas": ["S", "M", "L"],
                "oferta": {"precio": 8991, "descuento": 10, "termina": "30 de noviembre de 2026"},
            },
            {
                "nombre": "Correa Paseo Seguro",
                "tipo": "correa para mascota",
                "palabras_clave": "correa mascota paseo",
                "precio_normal": 14990,
                "stock": 6,
                "tallas": ["Único"],
                "oferta": {"precio": 11992, "descuento": 20, "termina": "30 de noviembre de 2026"},
            },
            {
                "nombre": "Cama Nube para Mascota",
                "tipo": "cama para mascota",
                "palabras_clave": "cama mascota descanso",
                "precio_normal": 32990,
                "stock": 3,
                "tallas": ["S", "M", "L"],
                "oferta": None,
            },
            {
                "nombre": "Juguete Mordedor Estrella",
                "tipo": "juguete para mascota",
                "palabras_clave": "juguete mordedor mascota perro gato",
                "precio_normal": 7990,
                "stock": 0,
                "tallas": ["Único"],
                "oferta": None,
            },
        ],
    },
    "muebles": {
        "tienda": "Muebles Casa Serena",
        "local": 405,
        "piso": 1,
        "productos": [
            {
                "nombre": "Cama Nórdica Doble",
                "tipo": "cama",
                "palabras_clave": "cama mueble dormitorio dormir",
                "precio_normal": 249990,
                "stock": 2,
                "medida_cm": "150 x 200 x 105",
                "oferta": {"precio": 199992, "descuento": 20, "termina": "30 de noviembre de 2026"},
            },
            {
                "nombre": "Cómoda Roble Claro",
                "tipo": "cómoda",
                "palabras_clave": "comoda cajonera mueble almacenamiento",
                "precio_normal": 159990,
                "stock": 4,
                "medida_cm": "100 x 45 x 90",
                "oferta": {"precio": 143991, "descuento": 10, "termina": "30 de noviembre de 2026"},
            },
            {
                "nombre": "Lámpara de Pie Alba",
                "tipo": "lámpara",
                "palabras_clave": "lampara luz iluminacion mueble",
                "precio_normal": 49990,
                "stock": 7,
                "medida_cm": "30 x 30 x 160",
                "oferta": None,
            },
        ],
    },
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(letra for letra in texto if unicodedata.category(letra) != "Mn")


_PALABRAS_IGNORADAS = {
    "de", "para", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "tienen", "tiene", "hay", "que", "del", "al", "me", "mi", "por",
    "favor", "dime", "muestra", "busco", "quiero", "necesito", "disponible",
    "disponibles", "stock", "cuanto", "cuanta", "cuantos", "cuantas", "mide",
    "medir", "talla", "tallas", "tono", "tonos", "color", "colores",
}

_PALABRAS_CLAVE_TIENDAS = {
    "calzado": {"calzado", "zapato"},
    "cosmetica": {"cosmetica", "cosmetico", "belleza", "maquillaje"},
    "mascotas": {"mascota"},
    "muebles": {"mueble", "hogar"},
}


def _palabras_importantes(texto: str) -> set[str]:
    """Normaliza, simplifica plurales y descarta palabras sin valor de búsqueda."""
    palabras = set()
    for palabra in re.findall(r"[a-z0-9]+", _normalizar(texto)):
        if palabra in _PALABRAS_IGNORADAS:
            continue
        if len(palabra) > 3 and palabra.endswith("es"):
            if palabra.endswith(("tes", "bles")):
                palabra = palabra[:-1]
            else:
                palabra = palabra[:-2]
        elif len(palabra) > 3 and palabra.endswith("s"):
            palabra = palabra[:-1]
        if palabra and palabra not in _PALABRAS_IGNORADAS:
            palabras.add(palabra)
    return palabras


def _tienda_coincide(filtro: str | None, categoria: str, tienda: dict) -> bool:
    if not filtro:
        return True
    palabras_filtro = _palabras_importantes(filtro)
    palabras_tienda = _palabras_importantes(f"{tienda['tienda']} {categoria}")
    palabras_clave = _PALABRAS_CLAVE_TIENDAS.get(categoria, set())
    return bool(palabras_filtro & (palabras_tienda | palabras_clave))


def _producto_para_respuesta(categoria: str, tienda: dict, producto: dict) -> dict:
    oferta = producto["oferta"]
    resultado = {
        "nombre": producto["nombre"],
        "tienda": tienda["tienda"],
        "local": tienda["local"],
        "piso": tienda["piso"],
        "precio": oferta["precio"] if oferta else producto["precio_normal"],
        "precio_normal": producto["precio_normal"],
        "stock": producto["stock"],
        "estado": "agotado" if producto["stock"] == 0 else "disponible",
    }
    for detalle in ("tallas", "tonos", "medida_cm"):
        if detalle in producto:
            resultado[detalle] = producto[detalle]
    resultado["oferta"] = oferta
    return resultado


@tool
def buscar_productos(texto: str, tienda: str | None = None, precio_max: int | None = None) -> list[dict] | str:
    """Busca productos del mall por nombre o tipo, con tienda y presupuesto opcionales."""
    consulta = _palabras_importantes(texto)
    resultados = []
    tipos_existentes = []
    for categoria, datos_tienda in _MALL.items():
        if not _tienda_coincide(tienda, categoria, datos_tienda):
            continue
        for producto in datos_tienda["productos"]:
            tipos_existentes.append(producto["tipo"])
            palabras_producto = _palabras_importantes(
                f"{producto['nombre']} {producto['tipo']} {producto['palabras_clave']}"
            )
            if consulta and not consulta.intersection(palabras_producto):
                continue
            resultado = _producto_para_respuesta(categoria, datos_tienda, producto)
            if precio_max is not None and resultado["precio"] > precio_max:
                continue
            resultados.append(resultado)
            if len(resultados) == 5:
                return resultados
    if resultados:
        return resultados
    tipos = ", ".join(dict.fromkeys(tipos_existentes)) or "ninguno"
    ubicacion = f" en {tienda}" if tienda else " en las tiendas del mall"
    return f"No encontré coincidencias{ubicacion}. Tipos de productos disponibles: {tipos}."


@tool
def ver_ofertas(tienda: str | None = None, precio_max: int | None = None) -> list[dict] | str:
    """Muestra productos en oferta en las cuatro tiendas, con filtros opcionales."""
    resultados = []
    for categoria, datos_tienda in _MALL.items():
        if not _tienda_coincide(tienda, categoria, datos_tienda):
            continue
        for producto in datos_tienda["productos"]:
            if not producto["oferta"]:
                continue
            resultado = _producto_para_respuesta(categoria, datos_tienda, producto)
            if precio_max is not None and resultado["precio"] > precio_max:
                continue
            resultados.append(resultado)
            if len(resultados) == 8:
                return resultados
    return resultados or "No encontré ofertas que coincidan con esos filtros."
