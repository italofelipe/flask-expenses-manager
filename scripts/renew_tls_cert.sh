#!/bin/sh
set -eu

# Renew Let's Encrypt certs (webroot) and reload nginx container.
#
# Usage:
#   ./scripts/renew_tls_cert.sh              # renew all certs if needed
#   ./scripts/renew_tls_cert.sh --dry-run    # ACME staging dry run
#
# Requirements:
# - docker compose stack running (reverse-proxy must be up for HTTP-01 challenges)
# - volumes `letsencrypt` + `certbot_challenge` must be the same as prod compose

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"

DRY_RUN="false"
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN="true"
fi

echo "[i15] ensuring reverse-proxy is running for ACME challenge..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d reverse-proxy

echo "[i15] running certbot renew..."
if [ "${DRY_RUN}" = "true" ]; then
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm certbot renew --dry-run
else
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm certbot renew --quiet
fi

echo "[i15] reloading nginx (reverse-proxy)..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T reverse-proxy nginx -s reload

echo "[i15] done"

