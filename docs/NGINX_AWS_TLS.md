# Nginx + TLS (AWS)

Updated at: 2026-02-10

## Scope
Operational guide for reverse proxy setup in AWS with Nginx + Certbot for `api.auraxis.com.br`.

## Preconditions
- `api.auraxis.com.br` resolves to EC2 public/elastic IP.
- Security Group allows inbound `80` and `443` from `0.0.0.0/0`.
- Stack is running via `docker-compose.prod.yml`.

## Initial HTTP mode
Default config (`deploy/nginx/default.conf`) serves HTTP and ACME challenge path:
- `/.well-known/acme-challenge/` -> shared webroot volume.
- Other routes proxied to Flask `web:8000`.

## Issue TLS certificate
1. Configure in `.env.prod`:
- `DOMAIN=api.auraxis.com.br`
- `CERTBOT_EMAIL=<your-email>`

2. Request certificate:
```bash
./scripts/request_tls_cert.sh
```

Equivalent manual command:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  --email "$CERTBOT_EMAIL" \
  -d "$DOMAIN" \
  --rsa-key-size 4096 \
  --agree-tos \
  --non-interactive
```

## Activate HTTPS config
After certificate issuance:
```bash
cp deploy/nginx/default.tls.conf deploy/nginx/default.conf
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --force-recreate reverse-proxy
```

## Validation
```bash
dig A api.auraxis.com.br +short
curl -I http://api.auraxis.com.br/docs/
curl -I https://api.auraxis.com.br/docs/
```

Expected:
- HTTP returns `301` after TLS config is enabled.
- HTTPS returns `200` with valid certificate chain.

## Renewal (recommended)
Use a cron entry on EC2 to renew and reload Nginx:
```bash
0 3 * * * cd /opt/auraxis && docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm certbot renew --quiet && docker compose --env-file .env.prod -f docker-compose.prod.yml exec reverse-proxy nginx -s reload
```

## Rollback
If TLS config fails:
```bash
git checkout -- deploy/nginx/default.conf
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --force-recreate reverse-proxy
```

## Security notes
- Keep SSH (`22`) restricted to your current public IPv4 `/32`.
- Never expose `5432` publicly.
- Prefer Elastic IP to avoid DNS drift after instance restart.
