"""Configuración central del proyecto.

Regla de la clase *Productivizar*: el código LEE la configuración, nunca la contiene.
Todo lo que cambia entre tu computador, el de un compañero o la nube vive en el .env.
"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _lista(valor: str | None) -> list[str]:
    """Convierte 'a, b ,c' en ['a', 'b', 'c'] sin vacíos ni barras finales."""
    return [u.strip().rstrip("/") for u in (valor or "").split(",") if u.strip()]


# Modelo. "prueba" usa un modelo determinista sin internet (tests y revisión sin clave).
GOOGLE_API_KEY: str = os.environ.get("GOOGLE_API_KEY", "")
MODELO: str = os.environ.get("MODELO", "gemini-3.5-flash-lite")

# Autenticación alternativa con Google OAuth / ADC (gcloud auth application-default login).
USAR_OAUTH: bool = os.environ.get("USAR_OAUTH", "").strip().lower() in ("1", "true", "si", "sí")
GOOGLE_CLOUD_PROJECT: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
GOOGLE_CLOUD_LOCATION: str = os.environ.get("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"

# Dónde escucha cada agente de este proyecto.
URL_VIAJES: str = os.environ.get("URL_VIAJES", "http://127.0.0.1:8000").rstrip("/")
URL_RESTAURANTES: str = os.environ.get("URL_RESTAURANTES", "http://127.0.0.1:8001").rstrip("/")
URL_COORDINADOR: str = os.environ.get("URL_COORDINADOR", "http://127.0.0.1:8002").rstrip("/")
URL_CHRISTIAN: str = os.environ.get("URL_CHRISTIAN", "http://127.0.0.1:8003").rstrip("/")

# Túnel: si existe, la ficha publica esta dirección en vez de la local (paso 10 de la clase).
URL_PUBLICA: str = os.environ.get("URL_PUBLICA", "").strip().rstrip("/")

# Agentes de compañeros (túneles), separados por comas.
URLS_AGENTES: list[str] = _lista(os.environ.get("URLS_AGENTES"))

# Límites (regla: toda llamada por red tiene timeout; todo ciclo tiene tope).
TIMEOUT_A2A: float = float(os.environ.get("TIMEOUT_A2A", "60"))
TIMEOUT_FICHA: float = float(os.environ.get("TIMEOUT_FICHA", "10"))
MAX_PASOS_AGENTE: int = int(os.environ.get("MAX_PASOS_AGENTE", "12"))
MAX_LARGO_PREGUNTA: int = int(os.environ.get("MAX_LARGO_PREGUNTA", "2000"))


# Contexto que el system prompt del patio de comidas recibe en cada conversación.
ZONA_HORARIA: str = os.environ.get("ZONA_HORARIA", "America/Santiago")
CANAL: str = os.environ.get("CANAL", "web")  # web, whatsapp, tótem, app


def ahora() -> datetime:
    """Fecha y hora actuales en Santiago. AHORA=2026-11-10T13:10 la fija (tests, ensayos, demos)."""
    fijo = os.environ.get("AHORA", "").strip()
    if fijo:
        return datetime.fromisoformat(fijo)
    return datetime.now(ZoneInfo(ZONA_HORARIA)).replace(tzinfo=None)


def modo_prueba() -> bool:
    """True cuando corremos sin Gemini (tests, CI o revisión sin clave)."""
    return MODELO.lower() == "prueba"


def exigir_clave() -> None:
    """Falla al arrancar, en una línea, si falta la clave (o credenciales OAuth) y no estamos en modo prueba."""
    if modo_prueba():
        return
    if USAR_OAUTH:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError

        try:
            _, proyecto_adc = google.auth.default()
        except DefaultCredentialsError:
            raise SystemExit(
                "Faltan credenciales OAuth (ADC). Ejecuta 'gcloud auth application-default login' "
                "o desactiva USAR_OAUTH y usa GOOGLE_API_KEY."
            ) from None
        if not (GOOGLE_CLOUD_PROJECT or proyecto_adc):
            raise SystemExit(
                "Falta GOOGLE_CLOUD_PROJECT en el .env para usar Google OAuth (ADC)."
            )
        return
    if not GOOGLE_API_KEY:
        raise SystemExit(
            "Falta GOOGLE_API_KEY en el .env (cópialo desde .env.example), o activa USAR_OAUTH=true. "
            "Para probar sin clave usa MODELO=prueba."
        )
