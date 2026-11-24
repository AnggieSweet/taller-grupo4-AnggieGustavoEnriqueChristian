#!/usr/bin/env bash
# Detiene los servicios levantados con iniciar.sh. Equivale a detener.ps1.
# Uso, desde la raíz del proyecto:  bash detener.sh

cd "$(dirname "$0")"
ARCHIVO_PIDS="logs/pids.txt"

if [ ! -f "$ARCHIVO_PIDS" ]; then
  echo "No se encontró $ARCHIVO_PIDS; no hay procesos registrados para detener."
  exit 0
fi

while IFS='|' read -r nombre pid; do
  [ -z "${pid:-}" ] && continue
  if kill "$pid" 2>/dev/null; then
    for _ in 1 2 3 4 5; do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -9 "$pid" 2>/dev/null
    echo "Detenido: $nombre"
  else
    echo "No se pudo detener $nombre (PID $pid); quizá ya no estaba activo."
  fi
done < "$ARCHIVO_PIDS"

rm -f "$ARCHIVO_PIDS"
echo "Se eliminó $ARCHIVO_PIDS."
