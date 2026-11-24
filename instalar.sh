#!/usr/bin/env bash
# Crea los entornos virtuales e instala las dependencias en Mac o Linux.
# Equivale a instalar.ps1. Uso, desde la raíz del proyecto:  bash instalar.sh
# Para elegir otro Python:  PYTHON=/ruta/a/python3.13 bash instalar.sh

set -euo pipefail
cd "$(dirname "$0")"

buscar_python() {
  if [ -n "${PYTHON:-}" ]; then echo "$PYTHON"; return; fi
  for candidato in python3.13 python3.12; do
    if command -v "$candidato" >/dev/null 2>&1; then echo "$candidato"; return; fi
  done
}

PYTHON_BASE="$(buscar_python)"
if [ -z "$PYTHON_BASE" ]; then
  echo "No se encontró Python 3.13 ni 3.12."
  echo "Mac: brew install python@3.13   Linux (Debian/Ubuntu): sudo apt install python3.13 python3.13-venv"
  exit 1
fi
echo "Usando $("$PYTHON_BASE" --version) ($PYTHON_BASE)"

instalar_entorno() {  # carpeta requisitos
  local carpeta=$1 requisitos=$2
  if [ ! -x "$carpeta/bin/python" ]; then
    echo "Creando $carpeta..."
    "$PYTHON_BASE" -m venv "$carpeta"
  fi
  echo "Instalando dependencias de $requisitos..."
  "$carpeta/bin/python" -m pip install --quiet --upgrade pip
  "$carpeta/bin/python" -m pip install --quiet -r "$requisitos"
}

instalar_entorno .venv requirements.txt
instalar_entorno .venv-crew requirements-crew.txt

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Se creó .env desde .env.example."
fi
if [ -f bruno/.env.example ] && [ ! -f bruno/.env ]; then
  cp bruno/.env.example bruno/.env
  echo "Se creó bruno/.env desde bruno/.env.example."
fi

echo
echo "Completa en .env las variables obligatorias: GOOGLE_API_KEY y API_KEY."
echo "  GOOGLE_API_KEY sin mostrarla:  .venv/bin/python -m scripts.configurar_clave"
echo "  API_KEY aleatoria:             .venv/bin/python -c \"import secrets; print(secrets.token_urlsafe(32))\""
echo "Opcionales para Telegram: TELEGRAM_TOKEN, TELEGRAM_SECRET y TELEGRAM_PERMITIDOS."
