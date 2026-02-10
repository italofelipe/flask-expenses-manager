#!/bin/sh
set -eu

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"
DOMAIN="${1:-${DOMAIN:-api.auraxis.com.br}}"
EMAIL="${2:-${CERTBOT_EMAIL:-}}"

if [ -z "${EMAIL}" ]; then
  echo "CERTBOT email is required. Set CERTBOT_EMAIL in ${ENV_FILE} or pass as second arg."
  exit 1
fi

echo "Ensuring reverse-proxy is running for ACME challenge..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d reverse-proxy

echo "Requesting certificate for ${DOMAIN}..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  --email "${EMAIL}" \
  -d "${DOMAIN}" \
  --rsa-key-size 4096 \
  --agree-tos \
  --non-interactive

echo "Certificate issued. To enable TLS config:"
echo "1) cp deploy/nginx/default.tls.conf deploy/nginx/default.conf"
echo "2) docker compose --env-file ${ENV_FILE} -f ${COMPOSE_FILE} up -d --force-recreate reverse-proxy"
