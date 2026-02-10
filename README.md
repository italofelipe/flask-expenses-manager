# Not Enough Cash, Stranger!

API RESTful para gestão financeira pessoal, construída com Flask, JWT e PostgreSQL.

## Stack atual
- Flask
- Flask-JWT-Extended
- Flask-SQLAlchemy / Flask-Migrate
- Marshmallow + Webargs (validação e serialização)
- Flask-Apispec (Swagger/OpenAPI)
- PostgreSQL

## Rodando com Docker

### Ambiente DEV
1. Crie o arquivo de ambiente de desenvolvimento:

```bash
cp .env.dev.example .env.dev
```

2. Suba os containers:

```bash
docker compose -f docker-compose.dev.yml up --build
```

### Ambiente PROD (local/staging)
1. Crie o arquivo de ambiente de produção:

```bash
cp .env.prod.example .env.prod
```

2. Suba os containers:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

3. Derrube os containers:

```bash
docker compose -f docker-compose.prod.yml down
```

## Portas e acesso
- DEV:
  - App exposto no host: `http://localhost:3333`
  - Swagger UI: `http://localhost:3333/docs/`
  - OpenAPI JSON: `http://localhost:3333/docs/swagger/`
  - PostgreSQL: `localhost:5432`
- PROD:
  - Nginx/reverse proxy: `http://localhost`
  - App interno (container): `web:8000`
  - TLS/HTTPS (quando habilitado): `https://api.auraxis.com.br`

## Deploy TLS (AWS)
- Guia completo de Nginx + Certbot:
  - `/opt/auraxis/docs/NGINX_AWS_TLS.md`

## Endpoints reais (código atual)

### Autenticação
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`

### Usuário
- `PUT /user/profile`
- `GET /user/me`

### Transações
- `POST /transactions`
- `PUT /transactions/{transaction_id}`
- `DELETE /transactions/{transaction_id}` (soft delete)
- `PATCH /transactions/restore/{transaction_id}`
- `GET /transactions/deleted`
- `DELETE /transactions/{transaction_id}/force` (hard delete)
- `GET /transactions/summary?month=YYYY-MM`
- `GET /transactions/list`

### Carteira / investimentos
- `POST /wallet`
- `GET /wallet`
- `GET /wallet/{investment_id}/history`
- `PUT /wallet/{investment_id}`
- `DELETE /wallet/{investment_id}`

## Documentação por controller
- `/opt/auraxis/docs/controllers/auth_controller.md`
- `/opt/auraxis/docs/controllers/user_controller.md`
- `/opt/auraxis/docs/controllers/transaction_controller.md`
- `/opt/auraxis/docs/controllers/wallet_controller.md`
- `/opt/auraxis/docs/API_RESPONSE_CONTRACT.md` (contrato alvo de resposta)
- `/opt/auraxis/docs/PHASE0_RESPONSE_ADOPTION_PLAN.md` (plano de adoção sem quebra)
- `/opt/auraxis/docs/PHASE0_IMPLEMENTATION_LOG.md` (log das entregas da Fase 0)
- `/opt/auraxis/docs/TESTING.md` (setup e execução da suíte)
- `/opt/auraxis/docs/CI_CD.md` (pipeline CI no GitHub Actions)

## Qualidade de código
Hooks configurados via `.pre-commit-config.yaml`:
- black
- isort
- flake8
- mypy

Execução manual:

```bash
pre-commit run --all-files
```

## Situação atual de testes
Existe suíte configurada em `tests/` com `pytest` e setup isolado de banco para execução local.

## Fase 0 (documentação e consistência)
Nesta fase, o foco é alinhar documentação com comportamento real e mapear lacunas sem alterar regras de negócio já funcionando.
