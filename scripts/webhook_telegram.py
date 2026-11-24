"""Apunta el webhook del bot de Telegram a una URL pública fija (por ejemplo, Heroku).

Uso, desde la raíz del proyecto:
    python -m scripts.webhook_telegram https://mi-app.herokuapp.com
    python -m scripts.webhook_telegram --borrar

Lee TELEGRAM_TOKEN y TELEGRAM_SECRET de .env (o del entorno); deben ser los
mismos que tiene configurados el servidor. Nunca imprime el token ni el secreto.
"""

from __future__ import annotations

import json
import os
import sys

import httpx
from dotenv import load_dotenv


TIMEOUT_TELEGRAM = 30.0


def _llamar(token: str, metodo: str, **datos: str) -> dict:
    try:
        respuesta = httpx.post(
            f"https://api.telegram.org/bot{token}/{metodo}", data=datos, timeout=TIMEOUT_TELEGRAM
        )
        cuerpo = respuesta.json()
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError(f"no se pudo contactar a Telegram ({type(error).__name__})") from None
    if not cuerpo.get("ok"):
        raise RuntimeError(f"Telegram respondió: {cuerpo.get('description', 'error')}")
    return cuerpo.get("result", {})


def main() -> int:
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    secreto = os.getenv("TELEGRAM_SECRET", "").strip()
    if not token or not secreto or secreto == "cambiame":
        print("Configura TELEGRAM_TOKEN y TELEGRAM_SECRET en .env.")
        return 1
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    try:
        if sys.argv[1] == "--borrar":
            _llamar(token, "deleteWebhook")
            print("Webhook borrado.")
            return 0
        base = sys.argv[1].rstrip("/")
        if not base.startswith("https://"):
            print("La URL debe empezar con https://")
            return 1
        _llamar(token, "setWebhook", url=f"{base}/telegram", secret_token=secreto)
        info = _llamar(token, "getWebhookInfo")
    except RuntimeError as error:
        print(str(error).replace(token, "[REDACTADO]"))
        return 1

    salida = json.dumps(
        {clave: info.get(clave) for clave in ("url", "pending_update_count", "last_error_message")},
        ensure_ascii=False,
        indent=2,
    )
    print(salida.replace(token, "[REDACTADO]").replace(secreto, "[REDACTADO]"))
    print("Listo: escribe al bot en Telegram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
