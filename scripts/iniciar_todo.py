"""Orquestador multiplataforma (Windows / macOS / Linux): levanta los 6 agentes A2A y la API FastAPI,
escribe sus registros en logs/<servicio>.log y detiene todo limpiamente con Ctrl+C.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

for flujo in (sys.stdout, sys.stderr):
    if hasattr(flujo, "reconfigure"):
        flujo.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parents[1]
LOGS = RAIZ / "logs"


def _python_entorno(nombre_venv: str) -> str:
    win = RAIZ / nombre_venv / "Scripts" / "python.exe"
    unix = RAIZ / nombre_venv / "bin" / "python"
    if win.is_file():
        return str(win)
    if unix.is_file():
        return str(unix)
    return sys.executable


def _tiene_modulo(py_bin: str, modulo: str) -> bool:
    """True si el intérprete py_bin puede importar `modulo` (sin importarlo de verdad)."""
    codigo = f"import importlib.util, sys; sys.exit(importlib.util.find_spec({modulo!r}) is None)"
    try:
        return subprocess.run([py_bin, "-c", codigo], cwd=str(RAIZ), timeout=30, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _puerto(url: str, defecto: int) -> int:
    parsed = urlparse(url)
    return parsed.port or defecto


def _esperar(nombre: str, url: str, proc: subprocess.Popen, timeout_s: float = 45.0) -> bool:
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        if proc.poll() is not None:
            print(f"✗ {nombre} terminó con código {proc.returncode}")
            return False
        try:
            r = httpx.get(url, timeout=2.0)
            if 200 <= r.status_code < 300:
                print(f"✓ {nombre:<14} activo ({url})")
                return True
        except Exception:
            pass
        time.sleep(0.4)
    print(f"✗ {nombre} no respondió en {url}")
    return False


def main() -> int:
    load_dotenv(RAIZ / ".env")
    LOGS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    py_gen = _python_entorno(".venv")
    py_crew = _python_entorno(".venv-crew")

    puerto_api = int(env.get("PORT") or env.get("API_PUERTO") or "8010")
    host_api = env.get("API_HOST", "127.0.0.1")
    host_check = "127.0.0.1" if host_api == "0.0.0.0" else host_api

    # En Heroku (variable DYNO) no hay .env ni archivos de log persistentes: las URL internas se
    # completan solas y los registros van a la consola para verlos con `heroku logs --tail`.
    en_paas = bool(env.get("DYNO"))
    if en_paas:
        env.setdefault("URL_VIAJES", "http://127.0.0.1:8000")
        env.setdefault("URL_RESTAURANTES", "http://127.0.0.1:8001")
        env.setdefault("URLS_AGENTES", ",".join(f"http://127.0.0.1:{p}" for p in (8003, 8004, 8005, 8006)))

    agentes = [
        ("viajes", py_gen, "src.agente_viajes.server:app", _puerto(env.get("URL_VIAJES", ""), 8000)),
        ("anggie", py_gen, "src.agente_anggie.server:app", _puerto(env.get("URL_ANGGIE", ""), 8003)),
        ("enrique", py_gen, "src.agente_enrique.server:app", _puerto(env.get("URL_ENRIQUE", ""), 8004)),
        ("algomarket", py_gen, "src.agente_algomarket.server:app", _puerto(env.get("URL_ALGOMARKET", ""), 8005)),
        ("christian", py_gen, "src.agente_christian.server:app", _puerto(env.get("URL_CHRISTIAN", ""), 8006)),
        ("restaurantes", py_crew, "src.agente_restaurantes.server:app", _puerto(env.get("URL_RESTAURANTES", ""), 8001)),
    ]

    # El agente de restaurantes necesita CrewAI (requirements-crew.txt). Si no está instalado
    # (p. ej. Heroku solo instala requirements.txt) se omite en vez de botar todo el sistema.
    if not _tiene_modulo(py_crew, "crewai"):
        print("! restaurantes omitido: CrewAI no está instalado (pip install -r requirements-crew.txt).")
        agentes = [a for a in agentes if a[0] != "restaurantes"]
        env["URL_RESTAURANTES"] = ""

    procesos: list[subprocess.Popen] = []
    archivos_log = []

    def _salida(nombre: str):
        if en_paas:
            return None  # hereda la consola del proceso web
        fh = (LOGS / f"{nombre}.log").open("w", encoding="utf-8")
        archivos_log.append(fh)
        return fh

    def detener(*_s) -> None:
        for p in reversed(procesos):
            if p.poll() is None:
                p.terminate()
        for p in reversed(procesos):
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        for fh in archivos_log:
            try:
                fh.close()
            except Exception:
                pass

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    try:
        for nombre, py_bin, modulo, puerto in agentes:
            fh = _salida(nombre)
            p = subprocess.Popen(
                [py_bin, "-m", "uvicorn", modulo, "--host", "127.0.0.1", "--port", str(puerto)],
                cwd=str(RAIZ),
                env=env,
                stdout=fh,
                stderr=subprocess.STDOUT if fh else None,
            )
            procesos.append(p)

        for (nombre, _, _, puerto), p in zip(agentes, procesos, strict=True):
            if not _esperar(nombre, f"http://127.0.0.1:{puerto}/.well-known/agent-card.json", p):
                detener()
                return 1

        fh_api = _salida("api")
        p_api = subprocess.Popen(
            [py_gen, "-m", "uvicorn", "api.app:app", "--host", host_api, "--port", str(puerto_api)],
            cwd=str(RAIZ),
            env=env,
            stdout=fh_api,
            stderr=subprocess.STDOUT if fh_api else None,
        )
        procesos.append(p_api)
        if not _esperar("api", f"http://{host_check}:{puerto_api}/health", p_api):
            detener()
            return 1

        print(f"\nSistema activo -> Swagger: http://localhost:{puerto_api}/docs (Ctrl+C para detener)", flush=True)
        while all(p.poll() is None for p in procesos):
            time.sleep(0.5)
        return 1
    except (KeyboardInterrupt, SystemExit):
        return 0
    finally:
        detener()


if __name__ == "__main__":
    sys.exit(main())
