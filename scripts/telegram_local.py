"""Publica temporalmente el webhook de Telegram usando un túnel quick tunnel."""

import asyncio
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv


logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


RUTA_CLOUDFLARED_WINDOWS = Path(
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
)
EXPRESION_URL = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
TIMEOUT_CLOUDFLARED = 60.0
TIMEOUT_SALUD = 120.0
TIMEOUT_TELEGRAM = 30.0


def _buscar_cloudflared() -> str | None:
    """Busca cloudflared en el PATH y en su ubicación habitual de Windows."""
    encontrado = shutil.which("cloudflared")
    if encontrado:
        return encontrado
    if RUTA_CLOUDFLARED_WINDOWS.is_file():
        return str(RUTA_CLOUDFLARED_WINDOWS)
    return None


async def _obtener_url_tunel(proceso: asyncio.subprocess.Process) -> str:
    """Lee la salida del túnel hasta obtener su URL pública temporal."""
    if proceso.stdout is None:
        raise RuntimeError("No se pudo leer la salida de cloudflared.")
    async with asyncio.timeout(TIMEOUT_CLOUDFLARED):
        while True:
            linea = await proceso.stdout.readline()
            if not linea:
                raise RuntimeError("cloudflared terminó antes de crear el túnel.")
            coincidencia = EXPRESION_URL.search(linea.decode("utf-8", errors="replace"))
            if coincidencia:
                return coincidencia.group(0).rstrip(".,;)")


async def _esperar_api(url: str) -> None:
    """Espera hasta 120 segundos a que el endpoint de salud responda correctamente."""
    fin = time.monotonic() + TIMEOUT_SALUD
    ultimo_motivo = "sin respuesta"
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as cliente:
        while True:
            restante = fin - time.monotonic()
            if restante <= 0:
                raise TimeoutError(
                    f"La API no respondió a /health en 120 segundos; último motivo: {ultimo_motivo}."
                )
            try:
                respuesta = await cliente.get(
                    f"{url}/health",
                    timeout=httpx.Timeout(min(5.0, restante)),
                )
                if not respuesta.is_success:
                    ultimo_motivo = f"código HTTP {respuesta.status_code}"
                elif not isinstance(respuesta.json(), dict):
                    ultimo_motivo = "respuesta JSON inválida"
                elif respuesta.json().get("ok") is True:
                    return
                else:
                    ultimo_motivo = "respuesta sin confirmación de salud"
            except httpx.TimeoutException:
                ultimo_motivo = "error de conexión (timeout)"
            except httpx.ConnectError as error:
                detalle = str(error).casefold()
                if any(pista in detalle for pista in ("getaddrinfo", "name resolution", "nodename", "dns")):
                    ultimo_motivo = "error DNS"
                else:
                    ultimo_motivo = "error de conexión"
            except httpx.RequestError:
                ultimo_motivo = "error de conexión"
            except ValueError:
                ultimo_motivo = "respuesta JSON inválida"
            await asyncio.sleep(min(3.0, max(0.0, fin - time.monotonic())))


def _sanear_salida(texto: str, token: str, secreto: str) -> str:
    """Evita mostrar el token o el secreto si aparecen en una respuesta externa."""
    if token:
        texto = texto.replace(token, "[REDACTADO]")
    if secreto:
        texto = texto.replace(secreto, "[REDACTADO]")
    return texto


async def _telegram_post(
    cliente: httpx.AsyncClient,
    token: str,
    metodo: str,
    **datos: str,
) -> dict:
    """Llama un método de Telegram sin revelar la URL que contiene el token."""
    respuesta = await cliente.post(
        f"https://api.telegram.org/bot{token}/{metodo}",
        data=datos,
        timeout=httpx.Timeout(TIMEOUT_TELEGRAM),
    )
    respuesta.raise_for_status()
    resultado = respuesta.json()
    if not resultado.get("ok"):
        raise RuntimeError("Telegram rechazó la solicitud.")
    return resultado


async def _cerrar_cloudflared(proceso: asyncio.subprocess.Process | None) -> None:
    """Termina cloudflared de forma ordenada y fuerza el cierre si es necesario."""
    if proceso is None or proceso.returncode is not None:
        return
    proceso.terminate()
    try:
        await asyncio.wait_for(proceso.wait(), timeout=5.0)
    except TimeoutError:
        proceso.kill()
        await proceso.wait()


async def ejecutar() -> int:
    """Configura el webhook y mantiene el túnel activo hasta Ctrl+C."""
    ruta_env = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(ruta_env, override=True)
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    secreto = os.getenv("TELEGRAM_SECRET", "").strip()
    if not token or not secreto:
        print("Configura TELEGRAM_TOKEN y TELEGRAM_SECRET en .env.")
        return 1

    cloudflared = _buscar_cloudflared()
    if not cloudflared:
        print(
            "No se encontró cloudflared. Instálalo con "
            "winget install --id Cloudflare.cloudflared o desde "
            "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/."
        )
        return 1

    proceso: asyncio.subprocess.Process | None = None
    cliente: httpx.AsyncClient | None = None
    webhook_configurado = False
    try:
        proceso = await asyncio.create_subprocess_exec(
            cloudflared,
            "tunnel",
            "--url",
            "http://localhost:8010",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        url_publica = await _obtener_url_tunel(proceso)
        print(f"URL del túnel: {url_publica}")
        await _esperar_api(url_publica)

        cliente = httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_TELEGRAM))
        await _telegram_post(
            cliente,
            token,
            "setWebhook",
            url=f"{url_publica}/telegram",
            secret_token=secreto,
        )
        webhook_configurado = True
        informacion = await _telegram_post(cliente, token, "getWebhookInfo")
        salida = json.dumps(informacion.get("result", {}), ensure_ascii=False, indent=2)
        print(_sanear_salida(salida, token, secreto))
        print("Escribe a tu bot en Telegram. Ctrl+C para detener")
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        raise
    except TimeoutError as error:
        print("No se pudo preparar Telegram: " + _sanear_salida(str(error), token, secreto))
        return 1
    except Exception as error:
        print(
            "No se pudo preparar Telegram: "
            + _sanear_salida(" ".join(str(error).splitlines()), token, secreto)
            if not isinstance(error, httpx.HTTPError)
            else f"No se pudo preparar Telegram ({type(error).__name__})."
        )
        return 1
    finally:
        if webhook_configurado and cliente is not None:
            try:
                await _telegram_post(cliente, token, "deleteWebhook")
            except Exception as error:
                print(f"No se pudo borrar el webhook ({type(error).__name__}).")
        if cliente is not None:
            await cliente.aclose()
        await _cerrar_cloudflared(proceso)
    return 0


def main() -> None:
    try:
        resultado = asyncio.run(ejecutar())
    except KeyboardInterrupt:
        resultado = 0
    except Exception as error:
        print(f"No se pudo ejecutar el túnel local ({type(error).__name__}).")
        resultado = 1
    raise SystemExit(resultado)


if __name__ == "__main__":
    main()
