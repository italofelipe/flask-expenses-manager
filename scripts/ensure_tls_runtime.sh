#!/bin/sh
set -eu

# Idempotent runtime edge switcher for reverse-proxy.
# - EDGE_TLS_MODE=alb:
#   - renders HTTP-only nginx config suitable for ALB TLS termination
#   - skips local certificate issuance entirely
# - EDGE_TLS_MODE=alb_dual:
#   - transitional mode for safe cutover to ALB HTTP origins
#   - requires an existing local certificate
#   - serves HTTP:80 for the new ALB target group while keeping HTTPS:443 alive
# - EDGE_TLS_MODE=instance_tls (default):
#   - if cert exists for DOMAIN: renders TLS nginx config and recreates reverse-proxy
#   - if cert does not exist:
#     - in PROD, optionally requests cert (AUTO_REQUEST_TLS_CERT=true)
#     - falls back to HTTP nginx config without breaking startup

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
EDGE_TLS_MODE="${EDGE_TLS_MODE:-$(read_env_value EDGE_TLS_MODE)}"
EDGE_TLS_MODE="${EDGE_TLS_MODE:-instance_tls}"

if [ -z "${DOMAIN}" ]; then
  echo "[tls] missing DOMAIN (arg/env/$ENV_FILE)."
  exit 2
fi

if [ ! -f "deploy/nginx/default.tls.conf" ] || [ ! -f "deploy/nginx/default.http.conf" ] || [ ! -f "deploy/nginx/default.alb.conf" ] || [ ! -f "deploy/nginx/default.alb_dual.conf" ]; then
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

render_alb_config() {
  sed "s/__DOMAIN__/${DOMAIN}/g" deploy/nginx/default.alb.conf > deploy/nginx/default.conf
  echo "[tls] mode=alb domain=${DOMAIN}"
}

render_alb_dual_config() {
  sed "s/__DOMAIN__/${DOMAIN}/g" deploy/nginx/default.alb_dual.conf > deploy/nginx/default.conf
  echo "[tls] mode=alb_dual domain=${DOMAIN}"
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

if [ "${EDGE_TLS_MODE}" = "alb" ]; then
  render_alb_config
  recreate_proxy
  exit 0
fi

if [ "${EDGE_TLS_MODE}" = "alb_dual" ]; then
  if cert_exists; then
    render_alb_dual_config
    recreate_proxy
    exit 0
  fi
  echo "[tls] EDGE_TLS_MODE=alb_dual requires an existing certificate for ${DOMAIN}."
  exit 4
fi

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
