#!/usr/bin/env bash

PUERTO="${1:-8000}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared no está instalado. Instálalo con: brew install cloudflared"
  exit 1
fi

cloudflared tunnel --url "http://127.0.0.1:${PUERTO}" 2>&1 | while IFS= read -r linea; do
  printf '%s\n' "$linea"
  if [[ "$linea" =~ (https://[[:alnum:]-]+\.trycloudflare\.com) ]]; then
    printf '\n\033[1;36m==============================================\n'
    printf 'DIRECCIÓN PÚBLICA: %s\n' "${BASH_REMATCH[1]}"
    printf '==============================================\033[0m\n'
    printf 'Pega esta dirección en URL_PUBLICA de tu .env y reinicia tu agente; pásasela a tu compañero para que la ponga en su URLS_AGENTES.\n\n'
  fi
done
