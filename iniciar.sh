#!/usr/bin/env bash
# Levanta los agentes y la API en segundo plano en Mac o Linux.
# Equivale a iniciar.ps1. Uso, desde la raíz del proyecto:  bash iniciar.sh
# Los registros quedan en logs/<servicio>.log. Para detener todo:  bash detener.sh

set -u
cd "$(dirname "$0")"
export PYTHONUTF8=1

PY=".venv/bin/python"
PY_CREW=".venv-crew/bin/python"
ARCHIVO_PIDS="logs/pids.txt"

if [ ! -f .env ]; then
  echo "No existe .env. Ejecuta primero: bash instalar.sh y completa su configuración."; exit 1
fi
if [ ! -x "$PY" ] || [ ! -x "$PY_CREW" ]; then
  echo "Faltan entornos virtuales. Ejecuta: bash instalar.sh"; exit 1
fi
if [ -f "$ARCHIVO_PIDS" ]; then
  echo "Ya existe $ARCHIVO_PIDS. Ejecuta bash detener.sh antes de iniciar otra vez."; exit 1
fi

mkdir -p logs
: > "$ARCHIVO_PIDS"
FALLIDOS=""

puerto_ocupado() {
  (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
}

iniciar() {  # nombre python modulo puerto ruta_salud
  local nombre=$1 python=$2 modulo=$3 puerto=$4 ruta=$5
  if puerto_ocupado "$puerto"; then
    echo "  ✗ $nombre: el puerto $puerto está ocupado (cierra ese proceso o ejecuta bash detener.sh)"
    FALLIDOS="$FALLIDOS $nombre"; return
  fi
  nohup "$python" -m uvicorn "$modulo" --host 127.0.0.1 --port "$puerto" >>"logs/$nombre.log" 2>&1 &
  echo "$nombre|$!" >> "$ARCHIVO_PIDS"
  printf "  Esperando %s en el puerto %s..." "$nombre" "$puerto"
  for _ in $(seq 1 60); do
    if curl -fs -m 3 "http://127.0.0.1:$puerto$ruta" >/dev/null 2>&1; then
      echo " responde."; return
    fi
    sleep 1
  done
  echo " no respondió en 60 s (revisa logs/$nombre.log)."
  FALLIDOS="$FALLIDOS $nombre"
}

TARJETA="/.well-known/agent-card.json"
echo "Levantando servicios..."
iniciar viajes       "$PY"      src.agente_viajes.server:app       8000 "$TARJETA"
iniciar anggie       "$PY"      src.agente_anggie.server:app       8003 "$TARJETA"
iniciar enrique      "$PY"      src.agente_enrique.server:app      8004 "$TARJETA"
iniciar algomarket   "$PY"      src.agente_algomarket.server:app   8005 "$TARJETA"
iniciar christian    "$PY"      src.agente_christian.server:app    8006 "$TARJETA"
iniciar restaurantes "$PY_CREW" src.agente_restaurantes.server:app 8001 "$TARJETA"
iniciar api          "$PY"      api.app:app                        8010 /health

echo
if [ -n "$FALLIDOS" ]; then
  echo "Servicios que no respondieron:$FALLIDOS"
fi
echo "Swagger: http://localhost:8010/docs"
echo "Para detener: bash detener.sh"
