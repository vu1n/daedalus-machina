#!/bin/sh
set -eu

if [ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]; then
  echo "[cloudflared] Token detected. Starting tunnel in token mode..."
  exec cloudflared tunnel --no-autoupdate run --token "${CLOUDFLARE_TUNNEL_TOKEN}"
fi

echo "[cloudflared] No token provided. Using credentials.json + templated config."
if [ -z "${CLOUDFLARE_TUNNEL_ID:-}" ]; then
  echo "[cloudflared] ERROR: CLOUDFLARE_TUNNEL_ID is not set" >&2
  exit 1
fi

if [ ! -f /etc/cloudflared/credentials.json ]; then
  echo "[cloudflared] ERROR: /etc/cloudflared/credentials.json missing" >&2
  exit 1
fi

if [ ! -f /etc/cloudflared/config.tmpl.yml ]; then
  echo "[cloudflared] ERROR: /etc/cloudflared/config.tmpl.yml missing" >&2
  exit 1
fi

if command -v envsubst >/dev/null 2>&1; then
  envsubst < /etc/cloudflared/config.tmpl.yml > /etc/cloudflared/config.yml
else
  echo "[cloudflared] envsubst not found; using sed-based substitution."
  sed -e "s|\\${CLOUDFLARE_TUNNEL_ID}|${CLOUDFLARE_TUNNEL_ID}|g" \
      -e "s|\\${N8N_HOST}|${N8N_HOST}|g" \
      -e "s|\\${N8N_WEBHOOK_HOST}|${N8N_WEBHOOK_HOST}|g" \
      -e "s|\\${N8N_SCRAPE_HOST}|${N8N_SCRAPE_HOST}|g" \
      -e "s|\\${N8N_SCRAPE_WEBHOOK_HOST}|${N8N_SCRAPE_WEBHOOK_HOST}|g" \
      /etc/cloudflared/config.tmpl.yml > /etc/cloudflared/config.yml
fi

exec cloudflared tunnel --config /etc/cloudflared/config.yml run

