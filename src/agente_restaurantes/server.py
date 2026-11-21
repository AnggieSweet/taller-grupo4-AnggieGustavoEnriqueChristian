import os
from dotenv import load_dotenv
from src.comun.tarjeta import crear_tarjeta
from src.comun.servidor import crear_app
from src.agente_restaurantes.crew import responder

load_dotenv()

URL_RESTAURANTES = os.getenv("URL_RESTAURANTES", "http://127.0.0.1:8001")

tarjeta = crear_tarjeta(
    nombre="Agente de restaurantes",
    descripcion="Recomienda restaurantes en LIM, BOG y EZE por zona y tipo de comida. No reserva.",
    url=URL_RESTAURANTES,
    skills=[
        ("buscar_restaurantes", "Buscar restaurantes", "Busca restaurantes en una ciudad filtrados por tipo o zona.", "restaurantes de carne en Buenos Aires"),
        ("detalle_restaurante", "Detalle de restaurante", "Obtiene el detalle completo de un restaurante dado su nombre exacto.", "Central Restaurante"),
    ],
)

app = crear_app(tarjeta, responder)
