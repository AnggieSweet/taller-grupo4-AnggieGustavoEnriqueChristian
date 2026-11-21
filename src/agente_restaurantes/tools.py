from crewai.tools import tool

# Datos inventados de restaurantes para LIM, BOG y EZE
RESTAURANTES = {
    "LIM": [
        {"nombre": "Central Restaurante", "zona": "Barranco", "tipo": "peruana contemporánea", "precio_medio_clp": 120000, "horario": "13:00 - 23:00"},
        {"nombre": "Maido", "zona": "Miraflores", "tipo": "nikkei", "precio_medio_clp": 110000, "horario": "12:30 - 22:30"},
        {"nombre": "La Mar Cebichería", "zona": "Miraflores", "tipo": "mariscos", "precio_medio_clp": 45000, "horario": "12:00 - 17:00"},
        {"nombre": "Punta Sal", "zona": "San Isidro", "tipo": "mariscos", "precio_medio_clp": 40000, "horario": "12:00 - 22:00"},
    ],
    "BOG": [
        {"nombre": "Andrés Carne de Res", "zona": "Chía", "tipo": "colombiana", "precio_medio_clp": 55000, "horario": "12:00 - 02:00"},
        {"nombre": "Leo", "zona": "Chapinero", "tipo": "colombiana contemporánea", "precio_medio_clp": 115000, "horario": "19:00 - 23:00"},
        {"nombre": "El Chato", "zona": "Chapinero", "tipo": "autor", "precio_medio_clp": 60000, "horario": "12:30 - 22:30"},
        {"nombre": "Criterion", "zona": "Zona G", "tipo": "francesa", "precio_medio_clp": 90000, "horario": "12:00 - 23:00"},
    ],
    "EZE": [
        {"nombre": "Don Julio", "zona": "Palermo", "tipo": "parrilla", "precio_medio_clp": 70000, "horario": "12:00 - 01:00"},
        {"nombre": "Corte Comestible", "zona": "Belgrano", "tipo": "parrilla", "precio_medio_clp": 50000, "horario": "12:30 - 00:00"},
        {"nombre": "Chila", "zona": "Puerto Madero", "tipo": "autor", "precio_medio_clp": 125000, "horario": "20:00 - 23:30"},
        {"nombre": "La Cabrera", "zona": "Palermo", "tipo": "parrilla", "precio_medio_clp": 65000, "horario": "12:00 - 00:00"},
    ],
}

@tool("buscar_restaurantes")
def buscar_restaurantes(ciudad: str, tipo: str) -> list:
    """Busca restaurantes en una ciudad (LIM, BOG, EZE) filtrados por tipo de comida o zona. Devuelve lista con nombre, zona, tipo, precio medio en CLP y horario."""
    ciudad = ciudad.upper()
    tipo = tipo.lower()
    lista = RESTAURANTES.get(ciudad, [])
    if not lista:
        return []
    # Filtrar por tipo o zona si coincide parcial
    filtrados = [r for r in lista if tipo in r["tipo"].lower() or tipo in r["zona"].lower() or tipo in "todos"]
    return filtrados if filtrados else lista

@tool("detalle_restaurante")
def detalle_restaurante(nombre: str) -> dict:
    """Obtiene el detalle completo de un restaurante dado su nombre exacto."""
    nombre = nombre.lower()
    for ciudad, lista in RESTAURANTES.items():
        for r in lista:
            if nombre in r["nombre"].lower():
                return dict(r, ciudad=ciudad)
    return {}
