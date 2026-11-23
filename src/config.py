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

# Dónde escucha cada agente y la API de este proyecto (configurables por entorno).
URL_VIAJES: str = os.environ.get("URL_VIAJES", "http://127.0.0.1:8000").rstrip("/")
URL_RESTAURANTES: str = os.environ.get("URL_RESTAURANTES", "http://127.0.0.1:8001").rstrip("/")
URL_COORDINADOR: str = os.environ.get("URL_COORDINADOR", "http://127.0.0.1:8002").rstrip("/")
URL_ANGGIE: str = os.environ.get("URL_ANGGIE", "http://127.0.0.1:8003").rstrip("/")
URL_ENRIQUE: str = os.environ.get("URL_ENRIQUE", "http://127.0.0.1:8004").rstrip("/")
URL_ALGOMARKET: str = os.environ.get("URL_ALGOMARKET", "http://127.0.0.1:8005").rstrip("/")
URL_CHRISTIAN: str = os.environ.get("URL_CHRISTIAN", "http://127.0.0.1:8006").rstrip("/")
API_HOST: str = os.environ.get("API_HOST", os.environ.get("HOST", "127.0.0.1")).strip() or "127.0.0.1"
API_PUERTO: int = int(os.environ.get("PORT") or os.environ.get("API_PUERTO") or "8010")

# Túnel: si existe, la ficha publica esta dirección en vez de la local (paso 10 de la clase).
URL_PUBLICA: str = os.environ.get("URL_PUBLICA", "").strip().rstrip("/")

# Agentes del catálogo separados por comas.
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
    return os.environ.get("MODELO", MODELO).lower() == "prueba"


def obtener_credenciales_oauth():
    """Obtiene credenciales Google OAuth válidas desde ADC o sesión activa de gcloud CLI."""
    import shutil
    import subprocess
    import time

    import google.auth
    from google.auth.exceptions import DefaultCredentialsError, RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    cache = getattr(obtener_credenciales_oauth, "_cache", None)
    if cache is not None and (time.monotonic() - cache[2]) < 2400:
        return cache[0], cache[1]

    proyecto_adc = ""
    try:
        creds, proyecto_adc = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not creds.valid:
            creds.refresh(Request())
        obtener_credenciales_oauth._cache = (creds, proyecto_adc or "", time.monotonic())  # type: ignore[attr-defined]
        return creds, proyecto_adc or ""
    except (DefaultCredentialsError, RefreshError):
        pass

    gcloud_bin = shutil.which("gcloud.cmd") or shutil.which("gcloud")
    if gcloud_bin:
        res = subprocess.run([gcloud_bin, "auth", "print-access-token"], capture_output=True, text=True, timeout=20)
        if res.returncode == 0 and res.stdout.strip():
            creds = Credentials(token=res.stdout.strip())
            if not proyecto_adc:
                res_p = subprocess.run([gcloud_bin, "config", "get-value", "project"], capture_output=True, text=True, timeout=10)
                if res_p.returncode == 0:
                    proyecto_adc = res_p.stdout.strip()
            obtener_credenciales_oauth._cache = (creds, proyecto_adc or "", time.monotonic())  # type: ignore[attr-defined]
            return creds, proyecto_adc or ""

    raise RuntimeError(
        "Faltan credenciales OAuth válidas. Ejecuta 'gcloud auth login' o configura GOOGLE_API_KEY en .env."
    )


def exigir_clave() -> None:
    """Falla al arrancar, en una línea, si falta la clave (o credenciales OAuth) y no estamos en modo prueba."""
    if modo_prueba():
        return
    usar_oauth = os.environ.get("USAR_OAUTH", "").strip().lower() in ("1", "true", "si", "sí") or USAR_OAUTH
    api_key = os.environ.get("GOOGLE_API_KEY", GOOGLE_API_KEY).strip()
    proyecto = os.environ.get("GOOGLE_CLOUD_PROJECT", GOOGLE_CLOUD_PROJECT).strip()
    if usar_oauth and not api_key:
        _, proyecto_adc = obtener_credenciales_oauth()
        if not (proyecto or proyecto_adc):
            raise RuntimeError("Falta GOOGLE_CLOUD_PROJECT en el .env para usar Google OAuth (ADC).")
        return
    if not api_key:
        raise RuntimeError(
            "Falta GOOGLE_API_KEY en el .env (cópialo desde .env.example), o activa USAR_OAUTH=true."
        )
