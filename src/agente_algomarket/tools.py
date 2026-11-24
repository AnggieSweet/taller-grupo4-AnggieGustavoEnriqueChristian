import unicodedata

from langchain.tools import tool

from src import config

# Datos sintéticos de productos del supermercado conservando precio en CLP y unidad explícita.
PRODUCTOS = {
    "leche": {"precio_clp": 1290, "unidad": "1 litro", "stock": 45, "pasillo": "3 - Lacteos", "oferta": "2x1 los martes"},
    "pan": {"precio_clp": 1890, "unidad": "1 kilo", "stock": 30, "pasillo": "5 - Panaderia", "oferta": "Sin oferta"},
    "arroz": {"precio_clp": 2490, "unidad": "1 kilo", "stock": 60, "pasillo": "2 - Granos", "oferta": "10% dcto. con tarjeta"},
    "aceite": {"precio_clp": 3990, "unidad": "1 litro", "stock": 25, "pasillo": "2 - Aceites", "oferta": "Sin oferta"},
    "detergente": {"precio_clp": 4590, "unidad": "1 botella", "stock": 18, "pasillo": "7 - Limpieza", "oferta": "Pack 2 por $8.000"},
    "bebidas": {"precio_clp": 1990, "unidad": "1 botella", "stock": 80, "pasillo": "8 - Bebidas", "oferta": "3x2 en gaseosas"},
    "alimento para mascotas": {
        "precio_clp": 12990, "unidad": "1 saco de 3 kilos", "stock": 22, "pasillo": "9 - Mascotas", "oferta": "Sin oferta",
        "alias": ["comida para mascotas", "comida de mascotas", "alimento de mascotas",
                  "alimento para perros", "comida para perros", "alimento para gatos", "comida para gatos"],
    },
}

_PALABRAS_VACIAS = {"de", "del", "para", "con", "y", "la", "el", "los", "las"}

HORARIOS = {
    "lunes": ("09:00", "21:00"),
    "martes": ("09:00", "21:00"),
    "miercoles": ("09:00", "21:00"),
    "jueves": ("09:00", "21:00"),
    "viernes": ("09:00", "22:00"),
    "sabado": ("10:00", "22:00"),
    "domingo": ("10:00", "20:00"),
}

_DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def _normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y sin espacios sobrantes."""
    base = unicodedata.normalize("NFD", texto.strip().lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _singular(palabra: str) -> str:
    """Quita la 's' final para tratar 'bebida' y 'bebidas' como el mismo producto."""
    return palabra[:-1] if len(palabra) > 3 and palabra.endswith("s") else palabra


def _dia_actual(desplazamiento: int = 0) -> str:
    """Día de la semana según la zona horaria del proyecto (hoy = 0, mañana = 1)."""
    return _DIAS[(config.ahora().weekday() + desplazamiento) % 7]


@tool
def buscar_producto(producto: str) -> dict:
    """Busca un producto del supermercado y devuelve su precio en pesos chilenos (CLP), unidad, stock, pasillo y oferta. Productos disponibles: leche, pan, arroz, aceite, detergente, bebidas y alimento para mascotas. Si el nombre no coincide exactamente, devuelve encontrado=False con sugerencias para preguntarle al usuario."""
    clave = _normalizar(producto)
    if not clave:
        return {"encontrado": False, "mensaje": "No indicaste qué producto buscar.", "sugerencias": list(PRODUCTOS)}

    for nombre, datos in PRODUCTOS.items():
        nombres_validos = [nombre, *datos.get("alias", [])]
        if any(_singular(clave) == _singular(_normalizar(n)) for n in nombres_validos):
            return {
                "encontrado": True,
                "producto": nombre,
                "precio_clp": datos["precio_clp"],
                "unidad": datos["unidad"],
                "stock": datos["stock"],
                "pasillo": datos["pasillo"],
                "oferta": datos["oferta"],
            }

    palabras = {_singular(p) for p in clave.split() if p not in _PALABRAS_VACIAS}
    sugerencias = [
        n for n in PRODUCTOS
        if {_singular(t) for t in n.split() if t not in _PALABRAS_VACIAS} & palabras
    ]
    return {
        "encontrado": False,
        "mensaje": "Producto no encontrado en el inventario.",
        "sugerencias": sugerencias,
    }


@tool
def horario_supermercado(dia: str) -> dict:
    """Devuelve el horario de apertura y cierre del supermercado segun el dia de la semana (lunes a domingo, también 'hoy' o 'mañana')."""
    clave = _normalizar(dia)
    if clave == "hoy":
        clave = _dia_actual(0)
    elif clave == "manana":
        clave = _dia_actual(1)
    horario = HORARIOS.get(clave)
    if not horario:
        return {"encontrado": False, "mensaje": "No tengo horario para ese dia."}
    apertura, cierre = horario
    return {"encontrado": True, "dia": clave, "apertura": apertura, "cierre": cierre}
