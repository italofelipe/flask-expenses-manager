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

## Rate limiting (baseline S2)
- Middleware de proteção ativo para:
  - `/auth/register` e `/auth/login` (chave por IP)
  - `/graphql`, `/transactions/*` e `/wallet/*` (chave por usuário, com fallback IP)
- Em excesso de requisições:
  - status `429`
  - headers `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `X-RateLimit-Rule`

Variáveis de ambiente principais:
- `RATE_LIMIT_ENABLED=true`
- `RATE_LIMIT_DEFAULT_LIMIT=300`
- `RATE_LIMIT_DEFAULT_WINDOW_SECONDS=60`
- `RATE_LIMIT_AUTH_LIMIT=20`
- `RATE_LIMIT_GRAPHQL_LIMIT=120`
- `RATE_LIMIT_TRANSACTIONS_LIMIT=180`
- `RATE_LIMIT_WALLET_LIMIT=180`
- `RATE_LIMIT_TRUST_PROXY_HEADERS=true` (recomendado em produção atrás de Nginx)

## GraphQL hardening (baseline S2)
- Proteções de transporte antes da execução:
  - tamanho máximo da query
  - profundidade máxima
  - complexidade máxima
  - limite de operações por documento

Variáveis de ambiente principais:
- `GRAPHQL_MAX_QUERY_BYTES=20000`
- `GRAPHQL_MAX_DEPTH=8`
- `GRAPHQL_MAX_COMPLEXITY=300`
- `GRAPHQL_MAX_OPERATIONS=3`
- `GRAPHQL_MAX_LIST_MULTIPLIER=50`

## Situação atual de testes
Existe suíte configurada em `tests/` com `pytest` e setup isolado de banco para execução local.

## Fase 0 (documentação e consistência)
Nesta fase, o foco é alinhar documentação com comportamento real e mapear lacunas sem alterar regras de negócio já funcionando.
