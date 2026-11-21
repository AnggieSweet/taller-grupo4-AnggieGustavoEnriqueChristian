import os
from dotenv import load_dotenv
from src.comun.tarjeta import crear_tarjeta
from src.comun.servidor import crear_app
from src.agente_algomarket.graph import responder

load_dotenv()

URL_ALGOMARKET = os.getenv("URL_ALGOMARKET", "http://127.0.0.1:8005")

tarjeta = crear_tarjeta(
    nombre="Agente de Algomarket",
    descripcion="Informa precio, stock, pasillo y ofertas de productos del supermercado del centro comercial, y su horario de atención. No vende ni reserva productos, no calcula despachos a domicilio y no responde sobre otras tiendas, restaurantes, cine ni estacionamiento del centro comercial.",
    url=URL_ALGOMARKET,
    tags=["supermercado", "precios", "horarios"],
    skills=[
        ("buscar_producto", "Buscar producto", "Devuelve precio, stock, pasillo y oferta vigente de un producto del supermercado.", "¿Cuánto cuesta la leche y en qué pasillo está?"),
        ("horario_supermercado", "Horario del supermercado", "Indica el horario de apertura y cierre del supermercado según el día.", "¿A qué hora abre el supermercado el sábado?"),
    ],
)

app = crear_app(tarjeta, responder)