"""uvicorn src.agente_christian.server:app --port 8003

La ficha es el currículum que leen los supervisores de los compañeros: dice qué SÍ y qué NO.
"""
from src import config
from src.agente_christian.graph import responder
from src.comun.servidor import crear_app
from src.comun.tarjeta import crear_tarjeta

DESCRIPCION = (
    "Christian, asistente del Patio de Comidas Terraza Sabores del Mall Portal Nativo (Santiago de Chile, datos "
    "sintéticos): recomienda locales y platos del patio, informa precios en CLP, promociones vigentes según el día y "
    "la hora, horarios, opciones veganas y sin gluten, alérgenos, medios de pago, Club Nativo y servicios del patio "
    "(Wi-Fi, baños, zona infantil, estacionamiento). No toma pedidos ni procesa pagos, no reserva mesas, no informa "
    "sobre tiendas del mall ni sobre restaurantes fuera de este patio (otras ciudades o países) y no da consejos "
    "médicos ni nutricionales."
)

tarjeta = crear_tarjeta(
    "Agente de Christian",
    DESCRIPCION,
    config.URL_CHRISTIAN,
    [
        ("buscar_platos", "Qué comer en el patio",
         "Locales, platos, precios, alérgenos, dietas y si el local está abierto ahora.",
         "Soy celíaco, ¿dónde puedo comer pizza en el patio de comidas del mall?"),
        ("promociones_vigentes", "Promociones de hoy",
         "Promociones del patio validadas contra el día y la hora.",
         "¿Qué promo conviene hoy para almorzar en Terraza Sabores?"),
        ("info_patio", "Servicios del patio",
         "Horario, pagos, Club Nativo, Wi-Fi, baños, zona infantil y estacionamiento del patio de comidas.",
         "¿Me validan el estacionamiento si como en el patio?"),
        ("calcular_total", "Calcular un total",
         "Total en CLP de un pedido con la carta del patio (no toma el pedido ni cobra).",
         "Somos 4, uno vegano, ¿cuánto nos sale con combos?"),
    ],
)
app = crear_app(tarjeta, responder)
