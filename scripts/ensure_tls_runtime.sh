#!/bin/sh
set -eu

# Idempotent runtime TLS switcher for reverse-proxy.
# - If cert exists for DOMAIN: renders TLS nginx config and recreates reverse-proxy.
# - If cert does not exist:
#   - in PROD, optionally requests cert (AUTO_REQUEST_TLS_CERT=true)
#   - falls back to HTTP nginx config without breaking startup

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
ENV_NAME="${1:-${AURAXIS_ENV:-prod}}"
DOMAIN_INPUT="${2:-}"
AUTO_REQUEST_TLS_CERT="${AUTO_REQUEST_TLS_CERT:-true}"

read_env_value() {
  key="$1"
  if [ ! -f "$ENV_FILE" ]; then
    return 0
  fi
  awk -F= -v k="$key" '$1==k {sub(/^[^=]*=/,""); print; exit}' "$ENV_FILE"
}

DOMAIN="${DOMAIN_INPUT:-${DOMAIN:-$(read_env_value DOMAIN)}}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-$(read_env_value CERTBOT_EMAIL)}"

if [ -z "${DOMAIN}" ]; then
  echo "[tls] missing DOMAIN (arg/env/$ENV_FILE)."
  exit 2
fi

if [ ! -f "deploy/nginx/default.tls.conf" ] || [ ! -f "deploy/nginx/default.http.conf" ]; then
  echo "[tls] missing nginx templates in deploy/nginx/."
  exit 3
fi

cert_exists() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm --entrypoint sh certbot \
    -c "[ -f '/etc/letsencrypt/live/${DOMAIN}/fullchain.pem' ] && [ -f '/etc/letsencrypt/live/${DOMAIN}/privkey.pem' ]" >/dev/null
}

render_http_config() {
  sed "s/__DOMAIN__/${DOMAIN}/g" deploy/nginx/default.http.conf > deploy/nginx/default.conf
  echo "[tls] mode=http domain=${DOMAIN}"
}

render_tls_config() {
  sed "s/__DOMAIN__/${DOMAIN}/g" deploy/nginx/default.tls.conf > deploy/nginx/default.conf
  echo "[tls] mode=tls domain=${DOMAIN}"
}

recreate_proxy() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --force-recreate reverse-proxy
}

request_certificate() {
  if [ -z "${CERTBOT_EMAIL}" ]; then
    echo "[tls] CERTBOT_EMAIL missing, skip cert request."
    return 1
  fi
  echo "[tls] requesting certificate for ${DOMAIN}..."
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d reverse-proxy
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm certbot certonly \
    --webroot -w /var/www/certbot \
    --email "${CERTBOT_EMAIL}" \
    -d "${DOMAIN}" \
    --rsa-key-size 4096 \
    --agree-tos \
    --non-interactive
}

if cert_exists; then
  render_tls_config
  recreate_proxy
  exit 0
fi

if [ "${ENV_NAME}" = "prod" ] && [ "${AUTO_REQUEST_TLS_CERT}" = "true" ]; then
  if request_certificate && cert_exists; then
    render_tls_config
    recreate_proxy
    exit 0
  fi
fi

render_http_config
recreate_proxy
exit 0
