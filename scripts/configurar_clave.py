"""Guarda GOOGLE_API_KEY en el .env sin mostrarla en pantalla.

Uso, desde la raíz del proyecto:
    python -m scripts.configurar_clave

- La clave se pega sin que se vea (como una contraseña) y nunca se imprime.
- Si no existe .env, se crea a partir de .env.example.
- Solo cambia la línea GOOGLE_API_KEY; el resto del .env queda igual.
- En Mac y Linux el .env queda legible solo por tu usuario.
- .env está en .gitignore: la clave no se sube a GitHub.
"""

from __future__ import annotations

import getpass
import os
import re
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_ENV = RAIZ / ".env"
ARCHIVO_EJEMPLO = RAIZ / ".env.example"
NOMBRE = "GOOGLE_API_KEY"


def _leer_base() -> str:
    if ARCHIVO_ENV.exists():
        return ARCHIVO_ENV.read_text(encoding="utf-8")
    if ARCHIVO_EJEMPLO.exists():
        print("No había .env; se crea a partir de .env.example.")
        return ARCHIVO_EJEMPLO.read_text(encoding="utf-8")
    return ""


def _con_clave(contenido: str, clave: str) -> str:
    linea = f"{NOMBRE}={clave}"
    patron = re.compile(rf"^{NOMBRE}=.*$", re.MULTILINE)
    if patron.search(contenido):
        return patron.sub(lambda _: linea, contenido, count=1)
    separador = "" if not contenido or contenido.endswith("\n") else "\n"
    return f"{contenido}{separador}{linea}\n"


def _guardar(contenido: str) -> None:
    temporal = ARCHIVO_ENV.with_name(".env.tmp")
    descriptor = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
        archivo.write(contenido)
    os.replace(temporal, ARCHIVO_ENV)
    try:
        os.chmod(ARCHIVO_ENV, 0o600)
    except OSError:
        pass  # Windows no usa estos permisos.


def main() -> int:
    print(f"Pega tu {NOMBRE} y pulsa Enter (no se verá lo que escribes).")
    try:
        clave = getpass.getpass("Clave: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado; no se cambió nada.")
        return 1

    if not clave:
        print("No pegaste ninguna clave; no se cambió nada.")
        return 1
    if any(caracter.isspace() for caracter in clave) or "=" in clave or "#" in clave:
        print("La clave tiene espacios o caracteres no válidos; no se cambió nada.")
        return 1
    if not clave.startswith("AIza"):
        print("Aviso: las claves de Gemini suelen empezar por 'AIza'. Se guarda igual.")

    _guardar(_con_clave(_leer_base(), clave))
    print(f"Listo: {NOMBRE} guardada en .env ({len(clave)} caracteres).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
