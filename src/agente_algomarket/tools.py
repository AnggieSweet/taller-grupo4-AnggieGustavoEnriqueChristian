from langchain.tools import tool

# Datos inventados pero creíbles de productos del supermercado
PRODUCTOS = {
    "leche": {"precio_clp": 1290, "stock": 45, "pasillo": "3 - Lacteos", "oferta": "2x1 los martes"},
    "pan": {"precio_clp": 1890, "stock": 30, "pasillo": "5 - Panaderia", "oferta": "Sin oferta"},
    "arroz": {"precio_clp": 2490, "stock": 60, "pasillo": "2 - Granos", "oferta": "10% dcto. con tarjeta"},
    "aceite": {"precio_clp": 3990, "stock": 25, "pasillo": "2 - Aceites", "oferta": "Sin oferta"},
    "detergente": {"precio_clp": 4590, "stock": 18, "pasillo": "7 - Limpieza", "oferta": "Pack 2 por $8.000"},
    "bebidas": {"precio_clp": 1990, "stock": 80, "pasillo": "8 - Bebidas", "oferta": "3x2 en gaseosas"},
}

# Horarios inventados por dia de la semana
HORARIOS = {
    "lunes": ("09:00", "21:00"),
    "martes": ("09:00", "21:00"),
    "miercoles": ("09:00", "21:00"),
    "miércoles": ("09:00", "21:00"),
    "jueves": ("09:00", "21:00"),
    "viernes": ("09:00", "22:00"),
    "sabado": ("10:00", "22:00"),
    "sábado": ("10:00", "22:00"),
    "domingo": ("10:00", "20:00"),
}


@tool
def buscar_producto(producto: str) -> dict:
    """Busca un producto del supermercado y devuelve su precio, stock, pasillo y oferta vigente. Productos disponibles: leche, pan, arroz, aceite, detergente y bebidas."""
    clave = producto.strip().lower()
    info = PRODUCTOS.get(clave)
    if not info:
        for nombre, datos in PRODUCTOS.items():
            if nombre in clave or clave in nombre:
                info = datos
                clave = nombre
                break
    if not info:
        return {"encontrado": False, "mensaje": "Producto no encontrado en el inventario."}
    return {
        "encontrado": True,
        "producto": clave,
        "precio_clp": info["precio_clp"],
        "stock": info["stock"],
        "pasillo": info["pasillo"],
        "oferta": info["oferta"],
    }


@tool
def horario_supermercado(dia: str) -> dict:
    """Devuelve el horario de apertura y cierre del supermercado segun el dia de la semana."""
    clave = dia.strip().lower()
    horario = HORARIOS.get(clave)
    if not horario:
        return {"encontrado": False, "mensaje": "No tengo horario para ese dia."}
    apertura, cierre = horario
    return {"encontrado": True, "dia": clave, "apertura": apertura, "cierre": cierre}