"""Herramientas con datos ficticios para planificar viajes."""

from langchain_core.tools import tool


_VUELOS = {
    ("SCL", "LIM"): [("LATAM", "08:15", "11:05", 158000), ("Sky Airline", "16:40", "19:30", 129000)],
    ("LIM", "SCL"): [("LATAM", "09:20", "14:10", 164000), ("JetSMART", "18:00", "22:50", 137000)],
    ("SCL", "BOG"): [("LATAM", "07:30", "12:45", 242000), ("Avianca", "15:10", "20:25", 268000)],
    ("BOG", "SCL"): [("LATAM", "09:00", "16:15", 251000), ("Avianca", "17:35", "00:50", 273000)],
    ("SCL", "EZE"): [("LATAM", "08:50", "10:55", 112000), ("JetSMART", "19:15", "21:20", 89000)],
    ("EZE", "SCL"): [("LATAM", "11:30", "13:45", 118000), ("Sky Airline", "20:10", "22:25", 97000)],
    ("LIM", "BOG"): [("Avianca", "07:45", "10:55", 146000), ("LATAM", "16:20", "19:30", 153000)],
    ("BOG", "LIM"): [("Avianca", "09:15", "12:25", 149000), ("LATAM", "18:05", "21:15", 157000)],
    ("LIM", "EZE"): [("LATAM", "08:10", "14:05", 218000), ("Avianca", "15:30", "21:25", 231000)],
    ("EZE", "LIM"): [("LATAM", "09:40", "13:35", 224000), ("Avianca", "17:00", "20:55", 237000)],
    ("BOG", "EZE"): [("Avianca", "07:20", "15:05", 286000), ("LATAM", "14:40", "22:25", 299000)],
    ("EZE", "BOG"): [("Avianca", "08:30", "14:20", 291000), ("LATAM", "16:15", "22:05", 304000)],
}

_CIUDADES = {
    "SCL": ("Santiago", "Chile"),
    "LIM": ("Lima", "Perú"),
    "BOG": ("Bogotá", "Colombia"),
    "EZE": ("Buenos Aires", "Argentina"),
}

_ALIAS_AEROPUERTO = {
    "SANTIAGO": "SCL", "SANTIAGO DE CHILE": "SCL", "CHILE": "SCL",
    "LIMA": "LIM", "PERU": "LIM", "PERÚ": "LIM",
    "BOGOTA": "BOG", "BOGOTÁ": "BOG", "COLOMBIA": "BOG",
    "BUENOS AIRES": "EZE", "ARGENTINA": "EZE",
}

_HOTELES = {
    "SCL": [("Hotel Mirador del Cerro", 82000, 3), ("Casa Lastarria", 116000, 4)],
    "LIM": [("Hotel Costa Verde", 74000, 3), ("Casa Miraflores", 108000, 4)],
    "BOG": [("Hotel Parque 93", 79000, 3), ("Casa La Candelaria", 99000, 4)],
    "EZE": [("Hotel Plaza San Telmo", 85000, 3), ("Casa Palermo Soho", 121000, 4)],
}


def _codigo_aeropuerto(lugar: str) -> str:
    lugar_normalizado = lugar.strip().upper()
    return _ALIAS_AEROPUERTO.get(lugar_normalizado, lugar_normalizado)


@tool
def buscar_vuelos(origen: str, destino: str, fecha: str) -> list[dict]:
    """Busca vuelos ficticios entre los aeropuertos SCL, LIM, BOG y EZE para una fecha."""
    ruta = (_codigo_aeropuerto(origen), _codigo_aeropuerto(destino))
    return [
        {
            "origen": ruta[0],
            "destino": ruta[1],
            "fecha": fecha,
            "aerolinea": aerolinea,
            "salida": salida,
            "llegada": llegada,
            "precio_clp": precio,
        }
        for aerolinea, salida, llegada, precio in _VUELOS.get(ruta, [])
    ]


@tool
def buscar_hoteles(ciudad: str, noches: int) -> list[dict]:
    """Busca hoteles ficticios en Santiago, Lima, Bogotá o Buenos Aires para una cantidad de noches."""
    codigo = _codigo_aeropuerto(ciudad)
    if noches <= 0:
        return []

    nombre_ciudad, pais = _CIUDADES.get(codigo, ("", ""))
    if not nombre_ciudad:
        return []

    return [
        {
            "hotel": nombre,
            "ciudad": nombre_ciudad,
            "pais": pais,
            "noches": noches,
            "precio_por_noche_clp": precio_noche,
            "precio_total_clp": precio_noche * noches,
            "estrellas": estrellas,
        }
        for nombre, precio_noche, estrellas in _HOTELES[codigo]
    ]
