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

    agentes = [
        ("viajes", py_gen, "src.agente_viajes.server:app", _puerto(env.get("URL_VIAJES", ""), 8000)),
        ("anggie", py_gen, "src.agente_anggie.server:app", _puerto(env.get("URL_ANGGIE", ""), 8003)),
        ("enrique", py_gen, "src.agente_enrique.server:app", _puerto(env.get("URL_ENRIQUE", ""), 8004)),
        ("algomarket", py_gen, "src.agente_algomarket.server:app", _puerto(env.get("URL_ALGOMARKET", ""), 8005)),
        ("christian", py_gen, "src.agente_christian.server:app", _puerto(env.get("URL_CHRISTIAN", ""), 8006)),
        ("restaurantes", py_crew, "src.agente_restaurantes.server:app", _puerto(env.get("URL_RESTAURANTES", ""), 8001)),
    ]

    procesos: list[subprocess.Popen] = []
    archivos_log = []

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
            fh = (LOGS / f"{nombre}.log").open("w", encoding="utf-8")
            archivos_log.append(fh)
            p = subprocess.Popen(
                [py_bin, "-m", "uvicorn", modulo, "--host", "127.0.0.1", "--port", str(puerto)],
                cwd=str(RAIZ),
                env=env,
                stdout=fh,
                stderr=subprocess.STDOUT,
            )
            procesos.append(p)

        for (nombre, _, _, puerto), p in zip(agentes, procesos, strict=True):
            if not _esperar(nombre, f"http://127.0.0.1:{puerto}/.well-known/agent-card.json", p):
                detener()
                return 1

        fh_api = (LOGS / "api.log").open("w", encoding="utf-8")
        archivos_log.append(fh_api)
        p_api = subprocess.Popen(
            [py_gen, "-m", "uvicorn", "api.app:app", "--host", host_api, "--port", str(puerto_api)],
            cwd=str(RAIZ),
            env=env,
            stdout=fh_api,
            stderr=subprocess.STDOUT,
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
