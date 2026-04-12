# Architecture Snapshot

## Visao geral
Auraxis API e um backend Flask com suporte a REST e GraphQL, focado em gestao financeira pessoal e planejamento de metas.

## Blocos principais
- `app/controllers/`: adapters REST por dominio.
- `app/graphql/`: schema, queries, mutations e seguranca GraphQL.
- `app/application/services/`: casos de uso e orquestracao de regra de negocio.
- `app/models/`: entidades e persistencia.
- `app/services/`: servicos de dominio/integracoes (ex.: BRAPI).
- `migrations/`: versionamento de schema (Alembic/Flask-Migrate).

## Dados e infraestrutura
- Banco principal: PostgreSQL.
- Cache/locks/rate-limit distribuido: Redis.
- Deploy: AWS EC2 com Docker Compose.
- Reverse proxy/TLS: Nginx + certificados.

## TLS e renovacao de certificados
- Certificado Let's Encrypt para `api.auraxis.com.br` emitido via Certbot (webroot) dentro do servico `certbot` do `docker-compose.prod.yml`.
- Renovacao automatica por cron diario as 03:00 UTC no host EC2 (`certbot renew --quiet` + `nginx -s reload`). Referencia: `docs/NGINX_AWS_TLS.md`.
- Drill mensal `certbot renew --dry-run` documentado em `docs/runbooks/tls-renewal-drill.md` (INF-3 / SEC-hardening), com log de execucao e cadencia antes de cada janela de renovacao real.
- Sinais independentes de saude: alarme CloudWatch `auraxis.tls.days_to_expiry < 21` (INF-5) e monitor HTTPS UptimeRobot sobre `/healthz`.

## Qualidade e seguranca
- Pre-commit: ruff (format + lint + isort), bandit, mypy, gitleaks.
- CI: suites de testes, gates de seguranca e policy Sonar.
- Observabilidade: metricas e logs estruturados, com runbooks em `docs/`.

## Continuidade operacional (backup/DR)
- Backup diario automatico em `s3://auraxis-db-backups/daily/` via GH Actions workflow `db-backup.yml` (05:00 UTC). Lifecycle S3 expira objetos em 30 dias (prod) / 7 dias (dev).
- Scripts-chave: `scripts/backup-db-to-s3.sh`, `scripts/verify-backup.sh`, `scripts/restore-db-from-s3.sh`, `scripts/aws_backups_s3.py`.
- Runbook de disaster recovery: `docs/runbooks/disaster-recovery.md` — cobre EC2 failure, DB corruption e bad-deploy rollback, com RTO 4h / RPO 24h e drill mensal de restore em DB scratch.

## Principio arquitetural atual
Dominio centralizado com adapters REST/GraphQL finos para reduzir duplicacao e manter paridade de comportamento.
