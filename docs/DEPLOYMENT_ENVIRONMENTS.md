# Deployment Environments (DEV and PROD)

Updated at: 2026-02-10

## Goal
Establish explicit local/staging runtime profiles for development and production, keeping backward compatibility and reducing deployment risks.

## Files introduced
- `docker-compose.dev.yml`: local development stack.
- `docker-compose.prod.yml`: production-like stack.
- `Dockerfile.prod`: production image with gunicorn.
- `scripts/entrypoint_prod.sh`: startup orchestration (db wait + migrations + gunicorn).
- `deploy/nginx/default.conf`: reverse proxy to Flask app.
- `.env.dev.example`: development environment variables template.
- `.env.prod.example`: production environment variables template.

## DEV profile
- Uses `docker-compose.dev.yml`.
- Uses `.env.dev` through `env_file`.
- `AUTO_CREATE_DB=true` to keep local onboarding simple.
- Runs Flask development server (`flask run`).
- Exposes app on `localhost:3333`.

### Commands
```bash
cp .env.dev.example .env.dev
docker compose -f docker-compose.dev.yml up --build
```

## PROD profile
- Uses `docker-compose.prod.yml`.
- Uses `.env.prod` through `env_file`.
- `AUTO_CREATE_DB=false` and migrations via `flask db upgrade` on startup.
- Runs Gunicorn behind Nginx.
- Exposes app on `localhost:80`.
- Supports TLS with Certbot + Nginx (`443`) using shared challenge/certificate volumes.

### Commands
```bash
cp .env.prod.example .env.prod
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml down
```

### TLS enablement (AWS/domain)
```bash
./scripts/request_tls_cert.sh
cp deploy/nginx/default.tls.conf deploy/nginx/default.conf
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --force-recreate reverse-proxy
```

Detailed runbook:
- `docs/NGINX_AWS_TLS.md`

## Compatibility note
- `app/__init__.py` now gates `db.create_all()` using `AUTO_CREATE_DB`.
- Default remains `true` for local compatibility.
- Production compose explicitly sets `AUTO_CREATE_DB=false`.

## Security note
- Never commit `.env.dev`/`.env.prod` with real secrets.
- Prefer GitHub Actions secrets + runtime environment configuration for CI/CD and production.
