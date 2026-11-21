"""Herramientas del Agente de Christian · Patio de Comidas "Terraza Sabores" (Mall Portal Nativo).

Base de conocimiento: la del system prompt del patio (datos 100 % SINTÉTICOS para pruebas), pasada a
estructuras de Python. Así las reglas de oro se cumplen con código y no de memoria del modelo:
- horarios y promociones se validan contra el día y la hora reales (config.ahora());
- precios y totales salen siempre de aquí, en CLP con punto de miles;
- cada respuesta sobre dietas o alérgenos trae la advertencia de contaminación cruzada.
Ninguna herramienta toma pedidos ni procesa pagos. Si piden algo que no está, lo dicen en una línea.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from langchain_core.tools import tool

from src import config

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ALERGENOS = {"G": "gluten", "L": "lácteos", "H": "huevo", "M": "maní", "FC": "frutos de cáscara",
             "P": "pescado", "MA": "mariscos", "S": "soya", "SE": "sésamo"}
ADVERTENCIA = ("Importante: hay riesgo de contaminación cruzada en cocinas compartidas. Si la alergia es severa "
               "(por ejemplo anafilaxia al maní o a mariscos), confirma con el personal del local antes de pedir.")
INFORMACIONES = "Informaciones del mall (Nivel 1, junto a la entrada principal, +56 2 2900 1000)"


def clp(n: int) -> str:
    """8990 → '$8.990'."""
    return "$" + f"{int(n):,}".replace(",", ".")


def norm(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar."""
    t = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


# ── Horarios ───────────────────────────────────────────────────────────────────
Horario = dict[int, tuple[str, str]]  # día (0=lunes) → (abre, cierra)


def _horario(lun_jue: tuple[str, str], vie_sab: tuple[str, str], dom: tuple[str, str]) -> Horario:
    return {0: lun_jue, 1: lun_jue, 2: lun_jue, 3: lun_jue, 4: vie_sab, 5: vie_sab, 6: dom}


GENERAL = _horario(("11:00", "21:30"), ("11:00", "22:30"), ("11:30", "21:00"))


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


# ── Locales ────────────────────────────────────────────────────────────────────
@dataclass
class Plato:
    nombre: str
    precio: int
    etiquetas: list[str] = field(default_factory=list)  # combo, vegano, vegetariano, sin_gluten, picante, infantil, …
    alergenos: list[str] = field(default_factory=list)
    nota: str = ""
    solo: tuple[str, str] | None = None  # franja en que se vende (cazuela: 12:00–16:00)


@dataclass
class Local:
    codigo: str
    nombre: str
    tipo: str
    sector: str
    horario: Horario
    espera: str
    platos: list[Plato]
    palabras: str = ""  # sinónimos para buscar (sushi, pizza, …)
    infantil: bool = False
    nota: str = ""
    acepta_efectivo: bool = True


P = Plato
LOCALES: dict[str, Local] = {l.codigo: l for l in [
    Local("T-02", "Brasa Andina", "pollo y parrilla", "Norte", GENERAL, "8–12 min", [
        P("Combo ¼ pollo + papas fritas + bebida 500 cc", 7490, ["combo", "sin_gluten"], [], "sin gluten: el pollo"),
        P("½ pollo a las brasas solo", 8990, ["sin_gluten"]),
        P("Pollo entero + papas familiares + ensalada chilena + bebida 1,5 L", 18990, ["compartir"], [], "para 3–4 personas"),
        P("Churrasco de vacuno en marraqueta", 6490, [], ["G"]),
        P("Lomo a lo pobre (lomo, papas, huevo, cebolla)", 10990, [], ["H"]),
        P("Ensalada chilena", 2490, ["vegano", "sin_gluten"]),
        P("Menú infantil (nuggets + papas + jugo)", 4990, ["infantil"], ["G", "H"]),
    ], "pollo asado brasas parrilla carne churrasco lomo", infantil=True),
    Local("T-03", "Sakura Express", "sushi y comida japonesa", "Norte",
          _horario(("12:00", "21:30"), ("12:00", "22:30"), ("12:00", "21:30")), "10–15 min", [
        P("Combo 20 piezas (hot + california + avocado) + gyozas x3", 11990, ["combo"], ["P", "MA", "G", "S", "SE", "H"]),
        P("Tabla 30 piezas mixta", 15990, [], ["P", "MA", "G", "S", "SE"]),
        P("Tabla 40 piezas para compartir", 20990, ["compartir"], ["P", "MA", "G", "S", "SE"]),
        P("Tabla Veggie 20 piezas", 9490, ["vegano"], ["G", "S", "SE"]),
        P("Gohan de salmón", 8490, [], ["P", "S", "SE"]),
        P("Ramen tonkotsu", 9990, [], ["G", "H", "S", "SE"]),
        P("Gyozas de cerdo x6", 4490, [], ["G", "S"]),
    ], "sushi japonesa japones ramen gyozas gohan salmon rolls",
          nota="Usa salsa de soya con gluten; tiene soya sin gluten (tamari) a pedido."),
    Local("T-04", "Dragón de Jade", "comida china / cantonesa", "Norte", GENERAL, "6–10 min", [
        P("Combo 1 plato + arroz chaufán + 1 rollito + bebida", 7990, ["combo"], ["G", "H", "S"]),
        P("Combo 2 platos + arroz chaufán + bebida", 9490, [], ["G", "H", "S"]),
        P("Pollo mongoliano", 6490, [], ["G", "S"]),
        P("Carne mongoliana", 6990, [], ["G", "S"]),
        P("Chapsui de verduras con tofu", 5990, ["vegano"], ["S", "G"]),
        P("Wantán frito x10", 3490, [], ["G", "H"]),
        P("Menú infantil (pollo agridulce + arroz)", 4490, ["infantil"], ["G", "H", "S"]),
    ], "china chino cantonesa chaufan wantan mongoliano chapsui", infantil=True, nota="Picante opcional."),
    Local("T-05", "Napoli Forno", "pizzas y pastas", "Centro", GENERAL, "12–18 min (horno a leña)", [
        P("Combo pizza individual (2 ingredientes) + bebida", 6990, ["combo", "vegetariano_posible"], ["G", "L"]),
        P("Pizza familiar Margherita", 12990, ["vegetariano", "compartir"], ["G", "L"]),
        P("Pizza familiar Napoli Especial (jamón serrano, rúcula, parmesano)", 15990, ["compartir"], ["G", "L"]),
        P("Pizza individual sin gluten (base certificada)", 8490, ["sin_gluten"], ["L"], "horno compartido"),
        P("Pizza vegana (queso vegetal, champiñones, pimentón)", 8990, ["vegano"], ["G"]),
        P("Lasaña boloñesa", 8990, [], ["G", "L", "H"]),
        P("Fettuccine Alfredo", 7990, ["vegetariano"], ["G", "L", "H"]),
        P("Menú infantil (pizza mini jamón-queso + jugo)", 4990, ["infantil"], ["G", "L"]),
    ], "pizza pizzas pasta pastas italiana lasana fettuccine", infantil=True),
    Local("T-06", "Fuente Criolla", "comida chilena / fuente de soda", "Centro", GENERAL, "5–10 min", [
        P("Combo completo italiano + papas + bebida", 5490, ["combo"], ["G", "H"]),
        P("Completo italiano", 3490, [], ["G", "H"]),
        P("Barros Luco", 6990, [], ["G", "L"]),
        P("Chacarero", 7290, [], ["G"]),
        P("Pastel de choclo (porción)", 7990, [], ["L", "H"]),
        P("Cazuela de vacuno", 6990, ["sin_gluten"], [], "solo almuerzo 12:00–16:00", ("12:00", "16:00")),
        P("Empanada de pino horneada", 2990, [], ["G", "H"]),
        P("Sopaipillas x3 con pebre", 1990, ["vegano"], ["G"]),
        P("Menú infantil (as de vacuno pequeño + jugo)", 4490, ["infantil"], ["G"]),
    ], "chilena chileno completo sandwich sanguche empanada cazuela pastel choclo barros luco chacarero sopaipillas",
          infantil=True),
    Local("T-07", "La Catrina", "comida mexicana", "Centro",
          _horario(("12:00", "21:30"), ("12:00", "22:30"), ("12:00", "21:30")), "7–12 min", [
        P("Combo 3 tacos + nachos + bebida", 8490, ["combo"], [], "eliges la proteína"),
        P("Burrito de carne asada", 7490, [], ["G", "L"]),
        P("Burrito vegano (porotos, arroz, guacamole)", 6990, ["vegano"], ["G"]),
        P("Bowl de birria (con consomé)", 8990, ["sin_gluten", "picante"]),
        P("Tacos al pastor x3", 5990, ["sin_gluten"], [], "tortilla de maíz"),
        P("Quesadilla de queso", 4990, ["vegetariano"], ["G", "L"]),
        P("Nachos con guacamole y queso", 5490, ["vegetariano", "sin_gluten"], ["L"]),
    ], "mexicana mexicano tacos taco burrito nachos quesadilla birria", nota="Cocina con picante 🌶️."),
    Local("T-08", "Ají Limeño", "comida peruana", "Sur", GENERAL, "10–15 min", [
        P("Combo lomo saltado + arroz + chicha morada", 9990, ["combo"], ["G", "S"]),
        P("Ceviche clásico", 9490, ["sin_gluten", "picante"], ["P"]),
        P("Ceviche mixto", 10990, ["sin_gluten"], ["P", "MA"]),
        P("Ají de gallina", 8490, [], ["L", "FC", "G"]),
        P("Causa limeña de pollo", 6990, ["sin_gluten"], ["H"]),
        P("Arroz chaufa de pollo", 7990, [], ["H", "S"]),
        P("Tallarín saltado vegetariano", 7490, ["vegetariano"], ["G", "S"]),
    ], "peruana peruano ceviche lomo saltado causa aji gallina chaufa pescado mariscos"),
    Local("T-09", "Raíz Verde", "saludable, vegano y vegetariano", "Sur",
          _horario(("11:00", "20:30"), ("11:00", "20:30"), ("11:00", "20:30")), "5–8 min", [
        P("Combo bowl + jugo natural 400 cc", 8490, ["combo", "vegano_posible"]),
        P("Bowl Buddha (quinoa, garbanzos, palta, hummus)", 7490, ["vegano", "sin_gluten", "bowl_vegano"], ["SE"]),
        P("Bowl Proteico (pollo grillado, arroz integral, brócoli)", 7990, ["sin_gluten"]),
        P("Hamburguesa de lentejas + papas rústicas", 7490, ["vegano"], ["G"]),
        P("Wrap falafel", 6490, ["vegano"], ["G", "SE"]),
        P("Ensalada César con pollo", 6990, [], ["G", "L", "H", "P"], "P por la anchoa"),
        P("Jugo natural 400 cc (frutilla, mango, verde detox)", 2990, ["vegano", "sin_gluten", "bebida"]),
    ], "saludable sano vegano vegana vegetariano vegetariana bowl ensalada jugo wrap falafel lentejas",
          nota="Cocina 100 % libre de maní."),
    Local("T-10", "Smash Bros Burger", "hamburguesas", "Sur", GENERAL, "8–12 min", [
        P("Combo Smash doble + papas + bebida", 8990, ["combo"], ["G", "L", "H", "SE"]),
        P("Smash simple", 5490, [], ["G", "L", "H", "SE"]),
        P("Smash triple bacon", 8490, [], ["G", "L", "H", "SE"]),
        P("Burger Crispy Chicken", 6490, ["picante"], ["G", "H", "L"]),
        P("Burger Beyond (proteína vegetal)", 7490, ["vegano"], ["G", "SE", "S"]),
        P("Pan sin gluten (reemplazo)", 1000, ["sin_gluten", "extra"], [], "se agrega a cualquier burger (+$1.000) · plancha compartida"),
        P("Papas fritas grandes", 2990, ["vegano"], [], "freidora compartida"),
        P("Milkshake (vainilla, chocolate, manjar)", 3490, ["bebida"], ["L"]),
        P("Menú infantil (mini burger + papas + jugo)", 4990, ["infantil"], ["G", "L", "H"]),
    ], "hamburguesa hamburguesas burger burgers smash papas fritas milkshake", infantil=True),
    Local("T-11", "Shawarma Habibi", "comida árabe / mediterránea", "Este",
          _horario(("12:00", "21:30"), ("12:00", "22:30"), ("12:00", "21:30")), "5–8 min", [
        P("Combo shawarma + papas + bebida", 7990, ["combo"], ["G", "SE", "L"]),
        P("Shawarma de pollo", 5990, [], ["G", "SE", "L"]),
        P("Shawarma mixto (pollo-vacuno)", 6490, [], ["G", "SE", "L"]),
        P("Plato kebab con arroz y ensalada", 8490, ["sin_gluten"], ["SE", "L"]),
        P("Falafel x6 con hummus", 4990, ["vegano"], ["SE"]),
        P("Baklava x2", 2990, ["postre"], ["G", "FC", "L"]),
    ], "arabe arabes mediterranea shawarma kebab falafel hummus baklava"),
    Local("T-12", "Dulce Brisa", "café, pastelería y postres", "Este",
          _horario(("10:30", "21:30"), ("10:30", "22:30"), ("11:00", "21:00")), "3–6 min", [
        P("Combo café + trozo de torta", 5490, ["combo"]),
        P("Café americano / espresso", 2290, ["vegano", "bebida"]),
        P("Cappuccino / latte", 2990, ["bebida"], ["L"], "leche de avena +$500"),
        P("Torta tres leches (trozo)", 3490, ["postre"], ["G", "L", "H"]),
        P("Cheesecake de frambuesa", 3790, ["postre"], ["G", "L", "H"]),
        P("Brownie sin gluten", 2790, ["sin_gluten", "postre"], ["L", "H", "FC"]),
        P("Medialuna", 1490, [], ["G", "L", "H"]),
        P("Kuchen de nuez", 3290, ["postre"], ["G", "L", "H", "FC"]),
    ], "cafe cafeteria pasteleria postre postres torta tortas medialuna once dulce brownie kuchen cheesecake",
          nota="⚠️ No acepta efectivo.", acepta_efectivo=False),
    Local("T-13", "Polo Norte Gelato", "heladería artesanal", "Este",
          _horario(("12:00", "22:00"), ("12:00", "22:30"), ("12:00", "22:00")), "2–5 min", [
        P("Cono 1 sabor", 2490, ["postre"]),
        P("Cono 2 sabores", 3290, ["postre"]),
        P("Vaso 3 sabores", 4290, ["postre"]),
        P("Litro para llevar", 9990, ["postre", "compartir"]),
        P("Paleta de fruta", 1990, ["vegano", "sin_gluten", "postre"]),
    ], "helado helados heladeria gelato cono paleta postre",
          nota="Sabores: vainilla, chocolate belga, pistacho (FC), manjar, frutilla 🌿, limón 🌿, mango 🌿, lúcuma, "
               "menta chips, sin azúcar (chocolate, frutos rojos)."),
    Local("T-14", "Poke Oceánico", "poke y bowls hawaianos", "Este",
          _horario(("11:30", "21:00"), ("11:30", "21:00"), ("11:30", "21:00")), "5–8 min", [
        P("Combo poke regular + bebida", 8990, ["combo", "vegano_posible", "sin_gluten_posible"], [], "arma tu bowl"),
        P("Poke regular (1 proteína, 4 toppings)", 7990, ["vegano_posible", "sin_gluten_posible"], [], "base: arroz, quinoa o mix verde"),
        P("Poke grande (2 proteínas, 5 toppings)", 9990, ["vegano_posible", "sin_gluten_posible"]),
        P("Topping extra", 700, ["extra"], [], "+$700: palta, mango, edamame (S), pepino, choclo, cebolla crispy (G)"),
    ], "poke hawaiano bowl bowls salmon atun camaron tofu",
          nota="Proteínas: salmón (P), atún (P), camarón (MA), pollo teriyaki (S, G), tofu 🌿 (S). "
               "Vegano: con tofu. Sin gluten: sin cebolla crispy ni pollo teriyaki."),
]}
EN_REMODELACION = {"T-15": "Local en remodelación. Próxima apertura: diciembre 2026, cocina coreana (nombre aún no "
                           "confirmado). No hay menú ni precios disponibles."}
CODIGOS_VALIDOS = set(LOCALES) | set(EN_REMODELACION) | {"T-01"}  # T-01: administración


def _estado(local: Local, ahora: datetime) -> tuple[bool, str]:
    """(abierto, texto) a la hora dada."""
    abre, cierra = local.horario[ahora.weekday()]
    hora = ahora.time()
    if _t(abre) <= hora < _t(cierra):
        faltan = (_t(cierra).hour * 60 + _t(cierra).minute) - (hora.hour * 60 + hora.minute)
        aviso = f" (cierra en {faltan} min)" if faltan <= 60 else ""
        return True, f"abierto hasta las {cierra}{aviso}"
    if hora < _t(abre):
        return False, f"cerrado, abre hoy a las {abre}"
    manana = (ahora.weekday() + 1) % 7
    return False, f"cerrado, ya cerró a las {cierra}; abre {DIAS[manana]} a las {local.horario[manana][0]}"


def _patio(ahora: datetime) -> str:
    abre, cierra = GENERAL[ahora.weekday()]
    if _t(abre) <= ahora.time() < _t(cierra):
        return f"el patio está abierto hasta las {cierra}"
    return f"el patio está cerrado (hoy {abre}–{cierra})"


def _ahora(dia: str = "", hora: str = "") -> datetime:
    """Ahora, o el día/hora que pida el usuario ('jueves', '19:30')."""
    base = config.ahora()
    if dia:
        d = next((i for i, n in enumerate(DIAS) if norm(n).startswith(norm(dia)[:3])), None)
        if d is not None:
            base = base + timedelta(days=(d - base.weekday()) % 7)  # el próximo día con ese nombre
    if hora and re.fullmatch(r"\d{1,2}:\d{2}", hora.strip()):
        h, m = hora.strip().split(":")
        base = base.replace(hour=int(h), minute=int(m))
    return base


def _contexto(ahora: datetime) -> str:
    return f"{DIAS[ahora.weekday()].capitalize()} {ahora:%d-%m-%Y} {ahora:%H:%M} · {_patio(ahora)}."


def _linea_plato(p: Plato, local: Local) -> str:
    marcas = []
    if "combo" in p.etiquetas:
        marcas.append("★ combo")
    for e, txt in [("vegano", "🌿 vegano"), ("vegano_posible", "🌿 vegano posible"), ("vegetariano", "🌱 vegetariano"),
                   ("vegetariano_posible", "🌱 vegetariano posible"), ("sin_gluten", "🚫🌾 sin gluten (puede haber trazas)"),
                   ("sin_gluten_posible", "🚫🌾 sin gluten posible"), ("picante", "🌶️ picante"),
                   ("infantil", "🧒 infantil")]:
        if e in p.etiquetas:
            marcas.append(txt)
    al = ", ".join(f"{a} ({ALERGENOS[a]})" for a in p.alergenos) if p.alergenos else "sin alérgenos declarados en la carta"
    extra = f" · {p.nota}" if p.nota else ""
    return f"  - {p.nombre} — {clp(p.precio)}{' · ' + ' · '.join(marcas) if marcas else ''} · Alérgenos: {al}{extra}"


# ── Herramienta 1 · buscar platos y locales ───────────────────────────────────
_DIETAS = {
    "vegano": {"vegano", "vegano_posible"}, "vegana": {"vegano", "vegano_posible"},
    "vegetariano": {"vegano", "vegano_posible", "vegetariano", "vegetariano_posible"},
    "vegetariana": {"vegano", "vegano_posible", "vegetariano", "vegetariano_posible"},
    "sin gluten": {"sin_gluten", "sin_gluten_posible"}, "celiaco": {"sin_gluten", "sin_gluten_posible"},
    "celiaca": {"sin_gluten", "sin_gluten_posible"}, "infantil": {"infantil"}, "ninos": {"infantil"},
    "picante": {"picante"}, "compartir": {"compartir"}, "postre": {"postre"},
}
_PALABRAS_ALERGENO = {"gluten": "G", "trigo": "G", "lacteo": "L", "lactosa": "L", "leche": "L", "huevo": "H",
                      "mani": "M", "cacahuate": "M", "nuez": "FC", "nueces": "FC", "frutos": "FC", "cascara": "FC",
                      "pescado": "P", "marisco": "MA", "mariscos": "MA", "camaron": "MA", "soya": "S", "soja": "S",
                      "sesamo": "SE"}
_RELLENO = set("a al algo bueno buena comer como con de del donde el en es esta hay la las los me mi para por que quiero "
               "rico rica un una y o ahora hoy patio local locales recomienda recomiendas almorzar cenar plato platos "
               "opcion opciones barato barata economico economica busco tienen soy alergico alergica puedo algun alguna "
               "tengo somos".split())


def _codigos_alergenos(texto: str) -> set[str]:
    cod = set()
    for palabra in re.findall(r"[a-z]+", norm(texto)):
        if palabra.upper() in ALERGENOS:
            cod.add(palabra.upper())
        for k, v in _PALABRAS_ALERGENO.items():
            if palabra.startswith(k[:5]) and len(palabra) >= 3:
                cod.add(v)
    return cod


def _local_por_texto(texto: str) -> Local | None:
    t = norm(texto).strip()
    m = re.search(r"t-?\s?(\d{1,2})", t)
    if m:
        return LOCALES.get(f"T-{int(m.group(1)):02d}")
    return next((l for l in LOCALES.values() if norm(l.nombre) in t or t in norm(l.nombre) and len(t) > 3), None)


@tool
def buscar_platos(consulta: str = "", dieta: str = "", sin_alergenos: str = "", presupuesto_max: int = 0,
                  local: str = "", solo_abiertos: bool = False) -> str:
    """Busca platos y locales del Patio de Comidas Terraza Sabores (Mall Portal Nativo) con su precio en CLP,
    alérgenos, etiquetas de dieta, tiempo de espera, sector y si el local está ABIERTO a la hora actual.
    consulta: antojo o tipo de comida ('sushi', 'pizza', 'chilena', 'hamburguesa', 'postre', 'helado', 'café').
    dieta: 'vegano', 'vegetariano', 'sin gluten' (celíaco), 'infantil', 'picante' o 'compartir'.
    sin_alergenos: alérgenos a evitar ('maní', 'mariscos, lácteos', 'gluten').
    presupuesto_max: precio máximo por plato en pesos (0 = sin tope).
    local: código o nombre ('T-05', 'Napoli Forno') para ver la carta completa de un local.
    solo_abiertos: True para mostrar solo locales abiertos ahora."""
    ahora = _ahora()
    salida = [f"Ahora: {_contexto(ahora)}"]
    if local and re.search(r"15", local):
        return EN_REMODELACION["T-15"]
    destino = _local_por_texto(local) if local else None
    if local and not destino:
        return f"No tengo un local '{local[:40]}' en el patio. Locales: " + ", ".join(
            f"{l.nombre} ({c})" for c, l in LOCALES.items()) + "."
    if not destino and re.search(r"corean", norm(consulta)):
        return EN_REMODELACION["T-15"]

    etiquetas = set()
    for k, v in _DIETAS.items():
        if k in norm(dieta) or k in norm(consulta):
            etiquetas |= v
    evitar = _codigos_alergenos(sin_alergenos)
    if etiquetas & {"sin_gluten"}:
        evitar.discard("G")  # ya filtrado por etiqueta
    terminos = [w for w in re.findall(r"[a-z0-9]+", norm(consulta)) if w not in _RELLENO and len(w) > 2
                and not any(w.startswith(k[:5]) for k in _DIETAS)]

    # Si ningún término calza con ningún local ni plato ("soy alérgico", "qué puedo"), la búsqueda es general.
    todo = " ".join(norm(f"{l.nombre} {l.tipo} {l.palabras} " + " ".join(p.nombre for p in l.platos)) for l in LOCALES.values())
    terminos = [t for t in terminos if t in todo]

    encontrados: list[tuple[Local, list[Plato]]] = []
    for l in ([destino] if destino else LOCALES.values()):
        abierto, _ = _estado(l, ahora)
        if solo_abiertos and not abierto:
            continue
        texto_local = norm(f"{l.nombre} {l.tipo} {l.palabras}")
        coincide_local = not terminos or any(t in texto_local for t in terminos)
        platos = []
        for p in l.platos:
            if not destino and not coincide_local and not any(t in norm(p.nombre) for t in terminos):
                continue
            if etiquetas and not (set(p.etiquetas) & etiquetas):
                continue
            if evitar and set(p.alergenos) & evitar:
                continue
            if presupuesto_max and p.precio > presupuesto_max:
                continue
            if "extra" in p.etiquetas and not destino:
                continue
            platos.append(p)
        if platos:
            encontrados.append((l, sorted(platos, key=lambda x: x.precio)))

    if not encontrados:
        filtros = ", ".join(x for x in [consulta, dieta, f"sin {sin_alergenos}" if sin_alergenos else "",
                                        f"hasta {clp(presupuesto_max)}" if presupuesto_max else ""] if x)
        salida.append(f"No encontré platos con esos criterios ({filtros or 'sin filtros'}) en la carta del patio. "
                      "No inventes alternativas: ofrece buscar con otro criterio.")
        return "\n".join(salida)

    encontrados.sort(key=lambda x: (not _estado(x[0], ahora)[0], x[1][0].precio))
    for l, platos in encontrados[: (1 if destino else 6)]:
        _, estado = _estado(l, ahora)
        extras = [f"espera {l.espera}", f"Sector {l.sector}", estado]
        if l.infantil:
            extras.append("🧒 menú infantil")
        salida.append(f"**{l.nombre} ({l.codigo})** — {l.tipo} · " + " · ".join(extras))
        salida += [_linea_plato(p, l) for p in platos[: (20 if destino else 5)]]
        if l.nota:
            salida.append(f"  Nota: {l.nota}")
        for p in platos:
            if p.solo and not (_t(p.solo[0]) <= ahora.time() < _t(p.solo[1])):
                salida.append(f"  Ojo: {p.nombre} solo se vende de {p.solo[0]} a {p.solo[1]}.")
    if len(encontrados) > 6 and not destino:
        salida.append(f"(Hay {len(encontrados) - 6} locales más con resultados; pide afinar la búsqueda.)")
    if etiquetas & {"sin_gluten", "vegano", "vegetariano"} or evitar or re.search(r"alerg|celiac|intoleran", norm(consulta + dieta)):
        avisos = [ADVERTENCIA]  # va arriba: es lo primero que debe leer quien tiene una alergia
        if "M" in evitar:
            avisos.append("Maní: ningún plato lo declara, pero solo Raíz Verde (T-09) declara cocina 100 % libre de maní.")
        salida[1:1] = avisos
    return "\n".join(salida)


# ── Herramienta 2 · promociones vigentes ──────────────────────────────────────
@dataclass
class Promo:
    nombre: str
    dias: set[int]
    desde: str | None  # None = apertura
    hasta: str | None  # None = cierre
    detalle: str
    local: str | None = None  # None = transversal


TODOS = set(range(7))
PROMOS = [
    Promo("Martes de Combos", {1}, None, None, "20 % dcto. en el combo principal ★ de cada local. No acumulable con otras promos del local."),
    Promo("Happy Hour Terraza", {0, 1, 2, 3}, "17:00", "19:00", "Bebidas y jugos naturales a mitad de precio en todos los locales."),
    Promo("Menú Estudiante", {0, 1, 2, 3, 4}, "15:00", "18:00", "Con credencial vigente (TNE o universitaria): 15 % dcto. en cualquier plato principal."),
    Promo("Domingo Familiar", {6}, None, None, "Domingo y festivos: por cada plato adulto, 1 menú infantil gratis en locales con menú infantil 🧒 (T-02, T-04, T-05, T-06, T-10)."),
    Promo("Tarjeta Club Nativo", TODOS, None, None, "10 % dcto. adicional pagando con la Tarjeta Club Nativo. Sí es acumulable con las promos transversales."),
    Promo("Jueves de Familia", {3}, None, None, "Pollo entero completo a $15.990 (en vez de $18.990).", "T-02"),
    Promo("Miércoles Sakura", {2}, "17:00", None, "2x1 en Tabla 30 piezas ($15.990).", "T-03"),
    Promo("Lunes Dragón", {0}, None, None, "Segundo combo a $4.990.", "T-04"),
    Promo("Viernes Pizza Party", {4}, "18:00", None, "2 pizzas familiares a $22.990.", "T-05"),
    Promo("Menú del Día", {0, 1, 2, 3, 4}, "12:00", "16:00", "Entrada + fondo + postre + jugo $7.490.", "T-06"),
    Promo("Taco Tuesday", {1}, None, None, "Tacos x3 a $4.490 (no acumulable con Martes de Combos).", "T-07"),
    Promo("Sábado Marino", {5}, None, None, "Ceviche mixto + pisco sour sin alcohol (mocktail) $11.990.", "T-08"),
    Promo("Lunes Sin Carne", {0}, None, None, "25 % dcto. en todos los bowls veganos.", "T-09"),
    Promo("Smash Night", TODOS, "20:00", None, "Upgrade gratis a papas grandes en cualquier combo.", "T-10"),
    Promo("Once Dulce", {0, 1, 2, 3, 4}, "16:00", "18:00", "2 cafés + 2 medialunas $6.990.", "T-12"),
    Promo("Hora Polar", TODOS, "20:00", None, "Segundo cono a mitad de precio.", "T-13"),
]
FONDO_DEL_DIA = {0: "Porotos granados", 1: "Charquicán", 2: "Pastel de choclo", 3: "Cazuela",
                 4: "Pescado frito con puré (P, G)"}


def _franja(p: Promo, dia: int) -> tuple[str, str]:
    horario = LOCALES[p.local].horario if p.local else GENERAL
    abre, cierra = horario[dia]
    return p.desde or abre, p.hasta or cierra


def _cuando(p: Promo) -> str:
    dias = "todos los días" if p.dias == TODOS else (
        "lunes a jueves" if p.dias == {0, 1, 2, 3} else "lunes a viernes" if p.dias == {0, 1, 2, 3, 4}
        else ", ".join(DIAS[d] for d in sorted(p.dias)))
    if p.desde and p.hasta:
        return f"{dias} de {p.desde} a {p.hasta}"
    if p.desde:
        return f"{dias} desde las {p.desde} hasta el cierre"
    return f"{dias}, todo el día"


def _donde(p: Promo) -> str:
    return f"{LOCALES[p.local].nombre} ({p.local})" if p.local else "todo el patio"


@tool
def promociones_vigentes(dia: str = "", hora: str = "") -> str:
    """Promociones del patio validadas contra el día y la hora: las vigentes AHORA (transversales y de cada local),
    las que empiezan más tarde hoy, las que ya terminaron y cuándo aplican las demás. Incluye los precios de los
    combos ★ con el descuento de 'Martes de Combos' cuando aplica y la regla de acumulación.
    dia y hora son opcionales ('jueves', '19:30') para consultar otro momento; por defecto, ahora."""
    ahora = _ahora(dia, hora)
    d, h = ahora.weekday(), ahora.time()
    vigentes, mas_tarde, terminadas, otros = [], [], [], []
    for p in PROMOS:
        if d not in p.dias:
            otros.append(p)
            continue
        ini, fin = _franja(p, d)
        if _t(ini) <= h < _t(fin):
            vigentes.append((p, fin))
        elif h < _t(ini):
            mas_tarde.append((p, ini))
        else:
            terminadas.append(p)
    salida = [f"Ahora: {_contexto(ahora)}", "Vigentes ahora:"]
    for p, fin in vigentes:
        faltan = (_t(fin).hour * 60 + _t(fin).minute) - (h.hour * 60 + h.minute)
        pronto = f" · ⏰ termina en {faltan} min" if faltan <= 60 else f" · hasta las {fin}"
        extra = f" Fondo de hoy: {FONDO_DEL_DIA[d]}." if p.nombre == "Menú del Día" else ""
        salida.append(f"- **{p.nombre}** ({_donde(p)}){pronto}: {p.detalle}{extra}")
        if p.nombre == "Martes de Combos":
            for l in LOCALES.values():
                combo = next((x for x in l.platos if "combo" in x.etiquetas), None)
                if combo:
                    abierto, est = _estado(l, ahora)
                    salida.append(f"    · {l.nombre} ({l.codigo}) {combo.nombre}: ~~{clp(combo.precio)}~~ "
                                  f"{clp(round(combo.precio * 0.8))}{'' if abierto else ' (' + est + ')'}")
    if not vigentes:
        salida.append("- Ninguna en este momento.")
    if mas_tarde:
        salida.append("Más tarde hoy:")
        salida += [f"- **{p.nombre}** ({_donde(p)}) desde las {ini}: {p.detalle}" for p, ini in mas_tarde]
    if terminadas:
        salida.append("Ya terminaron hoy: " + "; ".join(f"{p.nombre} ({_cuando(p)})" for p in terminadas) + ".")
    if otros:
        salida.append("No aplican hoy (cuándo sí): " + "; ".join(f"{p.nombre} · {_donde(p)} · {_cuando(p)}" for p in otros) + ".")
    salida.append("Regla de acumulación: salvo la Tarjeta Club Nativo, ninguna promo se combina con otra; "
                  "el cliente elige la más conveniente.")
    return "\n".join(salida)


# ── Herramienta 3 · información del patio ─────────────────────────────────────
INFO = {
    "horario": "Horario general del patio: lunes a jueves 11:00–21:30 · viernes y sábado 11:00–22:30 · domingo y festivos 11:30–21:00. Cada local puede tener su propio horario.",
    "ubicacion": "Terraza Sabores está en el Nivel 3 del Mall Portal Nativo (Av. Los Aromos 4500, Santiago): ascensores A y C, escaleras mecánicas centrales.",
    "capacidad": "620 puestos; sector terraza exterior techada con 180 puestos, pet friendly.",
    "hora punta": "Hora punta: 13:00–14:30 y 19:30–21:00 (tiempos de espera +50 % aprox.).",
    "pedidos": "Cómo pedir: en la caja de cada local, por el QR de la mesa (pides y pagas desde el celular y te avisan por SMS cuando está listo) o en la Portal Nativo App (pedidos para retiro, acumula Puntos Nativo). Yo no tomo pedidos ni proceso pagos.",
    "pagos": "Medios de pago: todos los locales aceptan efectivo, débito, crédito, QR/billeteras móviles y Tarjeta Club Nativo. Excepción: Dulce Brisa (T-12) no acepta efectivo.",
    "club nativo": "Club Nativo: 1 Punto Nativo por cada $100 gastado (pagando con la app o presentando el RUT en caja). 500 puntos = $5.000 de descuento en cualquier local del patio. Socios Club Nativo Oro (≥ 3.000 puntos/año): 10 % de descuento permanente en bebidas.",
    "wifi": "Wi-Fi: red \"PortalNativo_Free\", sin clave, 2 horas por día.",
    "servicios": "Servicios: baños (incluye accesible y mudador) junto al local T-14 · zona infantil \"Mini Sabores\" (niños de 2 a 8 años, gratis, máx. 45 min, con un adulto en el patio) · 2 microondas públicos junto a T-01 · dispensador de agua gratuito.",
    "accesibilidad": "Accesibilidad: mesas accesibles señalizadas en cada sector, ascensor A con prioridad, menús en braille en Informaciones.",
    "estacionamiento": "Estacionamiento: con consumo ≥ $10.000 en el patio validas 2 horas gratis en la caja del local (presenta el ticket de estacionamiento).",
    "administracion": "Administración del patio: oficina T-01, lunes a sábado 10:00–20:00.",
    "reciclaje": "Retiro de bandejas: puntos de reciclaje con separación (orgánico, plástico, papel) en cada sector.",
    "reclamos": "Reclamos: Servicio al Cliente (Nivel 1, o formulario en portalnativo.cl/contacto). Si es un tema de higiene o seguridad alimentaria, avisa también al administrador del patio (oficina T-01).",
    "informaciones": f"Para tiendas y otros servicios del mall: {INFORMACIONES}.",
    "nutricion": "No tengo información calórica ni nutricional; consúltala directamente en el local.",
    "proximamente": EN_REMODELACION["T-15"],
}
_SINONIMOS_INFO = {
    "horario": "hora abre cierra cierran abren abierto horario hasta",
    "ubicacion": "donde queda ubicacion piso nivel llegar direccion",
    "capacidad": "capacidad puestos terraza mascota mascotas perro pet",
    "hora punta": "punta lleno espera fila demora",
    "pedidos": "pedir pedido qr app aplicacion retiro sms",
    "pagos": "pago pagar efectivo debito credito tarjeta billetera",
    "club nativo": "club puntos nativo fidelizacion oro descuento socio",
    "wifi": "wifi wi-fi internet red",
    "servicios": "bano banos mudador infantil ninos juegos microondas agua",
    "accesibilidad": "accesible accesibilidad silla ruedas braille discapacidad",
    "estacionamiento": "estacionamiento estacionar auto parking ticket",
    "administracion": "administracion administrador oficina",
    "reciclaje": "bandeja bandejas reciclaje basura",
    "reclamos": "reclamo reclamos queja quejas higiene intoxicacion problema",
    "informaciones": "tienda tiendas zapatillas cine mall informaciones",
    "nutricion": "calorias nutricion nutricional",
    "proximamente": "coreana coreano remodelacion t-15 nuevo",
}


@tool
def info_patio(tema: str = "") -> str:
    """Información general del Patio de Comidas Terraza Sabores: horario general, ubicación, hora punta, cómo pedir
    (caja, QR, app), medios de pago, Club Nativo y puntos, Wi-Fi, baños y mudador, zona infantil, microondas,
    accesibilidad, estacionamiento gratis, administración, reciclaje, reclamos e Informaciones del mall.
    tema: palabra clave ('wifi', 'estacionamiento', 'pagos', 'baños'); vacío = resumen con el horario y los temas."""
    ahora = _ahora()
    palabras = set(re.findall(r"[a-z0-9-]+", norm(tema)))
    temas = [k for k, sin in _SINONIMOS_INFO.items() if palabras & set(sin.split()) or norm(k) in norm(tema)]
    if not tema.strip():
        return f"Ahora: {_contexto(ahora)}\n{INFO['horario']}\n{INFO['ubicacion']}\nTemas disponibles: {', '.join(INFO)}."
    if not temas:
        return (f"No tengo información sobre '{tema[:40]}' del patio. Para otros temas del mall: {INFORMACIONES}. "
                f"Temas que sí tengo: {', '.join(INFO)}.")
    salida = [INFO[k] for k in temas[:4]]
    if "horario" in temas:
        salida.insert(0, f"Ahora: {_contexto(ahora)}")
    return "\n".join(salida)


# ── Herramienta 4 · calcular un total ─────────────────────────────────────────
def _buscar_plato(texto: str) -> tuple[Local, Plato] | str:
    local = None
    m = re.search(r"\(?\bt-?\s?(\d{1,2})\)?", norm(texto))
    if m:
        local = LOCALES.get(f"T-{int(m.group(1)):02d}")
        texto = texto[: m.start()] + texto[m.end():]
    terminos = [w for w in re.findall(r"[a-z0-9¼½]+", norm(texto)) if w not in {"de", "con", "y", "el", "la", "+"}]
    candidatos = []
    for l in ([local] if local else LOCALES.values()):
        for p in l.platos:
            nombre = norm(p.nombre)
            if terminos and all(t in nombre for t in terminos):
                candidatos.append((l, p))
    exactos = [c for c in candidatos if norm(c[1].nombre) == norm(texto).strip()]
    if len(exactos) == 1:
        return exactos[0]
    if len(candidatos) == 1:
        return candidatos[0]
    if not candidatos:
        return f"No encontré '{texto.strip()[:50]}' en la carta."
    return f"'{texto.strip()[:50]}' es ambiguo: " + "; ".join(f"{p.nombre} ({l.codigo})" for l, p in candidatos[:5])


@tool
def calcular_total(items: list[str], descuento_pct: int = 0) -> str:
    """Calcula el total en CLP de un pedido con los precios de la carta (no toma el pedido ni cobra).
    items: una línea por plato con cantidad y, si ayuda, el código del local, por ejemplo
    ["3 x Combo Smash doble (T-10)", "1 x Combo bowl + jugo natural (T-09)"]. Para un descuento solo en un ítem,
    agrega '-20%' al final de esa línea (ej. combo ★ en Martes de Combos).
    descuento_pct: descuento sobre el total (ej. 10 por Tarjeta Club Nativo). Usa promociones_vigentes antes de aplicar uno."""
    lineas, total, errores = [], 0, []
    for item in items[:20]:
        m = re.match(r"\s*(\d+)\s*[x×*]\s*(.+)", item, flags=re.I)
        cantidad, resto = (int(m.group(1)), m.group(2)) if m else (1, item)
        pct = 0
        md = re.search(r"-\s*(\d{1,2})\s*%\s*$", resto)
        if md:
            pct, resto = int(md.group(1)), resto[: md.start()]
        encontrado = _buscar_plato(resto)
        if isinstance(encontrado, str):
            errores.append(encontrado)
            continue
        l, p = encontrado
        unitario = round(p.precio * (100 - pct) / 100)
        sub = unitario * cantidad
        total += sub
        desc = f" con {pct} % dcto. ({clp(p.precio)} → {clp(unitario)})" if pct else ""
        lineas.append(f"- {cantidad} × {p.nombre} ({l.codigo}){desc}: {cantidad} × {clp(unitario)} = {clp(sub)}")
    if errores:
        lineas += [f"⚠️ {e}" for e in errores]
    if not total:
        return "\n".join(lineas) or "No hay ítems para sumar."
    lineas.append(f"Subtotal: {clp(total)}")
    if descuento_pct:
        final = round(total * (100 - descuento_pct) / 100)
        lineas.append(f"Descuento {descuento_pct} %: −{clp(total - final)} · Total: {clp(final)}")
        total = final
    else:
        lineas.append(f"Total: {clp(total)}")
    if total >= 10000:
        lineas.append("Con consumo ≥ $10.000 validan 2 horas de estacionamiento gratis en la caja del local.")
    return "\n".join(lineas)


HERRAMIENTAS = [buscar_platos, promociones_vigentes, info_patio, calcular_total]

# Todos los montos que pueden aparecer en una respuesta (los de la carta y de las promos).
PRECIOS_CONOCIDOS = ({clp(p.precio) for l in LOCALES.values() for p in l.platos}
                     | {"$15.990", "$4.990", "$22.990", "$7.490", "$4.490", "$11.990", "$6.990", "$5.000", "$100",
                        "$10.000", "$500", "$1.000", "$700", "$18.990"})
