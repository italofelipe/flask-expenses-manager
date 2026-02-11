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
- sonar-local-check

Execução manual:

```bash
pre-commit run --all-files
```

CI (`.github/workflows/ci.yml`) inclui gates de segurança:
- `pip-audit` (dependências Python)
- `bandit` (SAST, falha em severidade alta)
- `gitleaks` (secret scanning)
- `dependency-review` em PR (falha com vulnerabilidade nova `high+`)

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
- `RATE_LIMIT_BACKEND=redis` (em produção) ou `memory` (local/dev)
- `RATE_LIMIT_REDIS_URL=redis://redis:6379/0` (quando backend for redis)
- `RATE_LIMIT_FAIL_CLOSED=true` (recomendado em produção; retorna `503` se Redis indisponível)

## GraphQL hardening (baseline S2)
- Proteções de transporte antes da execução:
  - tamanho máximo da query
  - profundidade máxima
  - complexidade máxima
  - limite de operações por documento
- Autorização por recurso em mutações sensíveis:
  - `createTransaction` valida ownership de `tagId`, `accountId` e `creditCardId`
    para impedir referência cruzada entre usuários.

Variáveis de ambiente principais:
- `GRAPHQL_MAX_QUERY_BYTES=20000`
- `GRAPHQL_MAX_DEPTH=8`
- `GRAPHQL_MAX_COMPLEXITY=300`
- `GRAPHQL_MAX_OPERATIONS=3`
- `GRAPHQL_MAX_LIST_MULTIPLIER=50`
- `GRAPHQL_ALLOW_INTROSPECTION=false` (recomendado em produção)
- `GRAPHQL_PUBLIC_QUERIES=__typename`
- `GRAPHQL_PUBLIC_MUTATIONS=registerUser,login`
- `GRAPHQL_ALLOW_UNNAMED_OPERATIONS=false` (recomendado em produção)

## Hardening adicional de segurança
- Limite global de payload HTTP:
  - `MAX_REQUEST_BYTES=1048576` (1MB por padrão)
- Secrets fortes obrigatórios fora de DEV:
  - `SECURITY_ENFORCE_STRONG_SECRETS=true`
- CORS por allowlist:
  - `CORS_ALLOWED_ORIGINS=https://app.auraxis.com.br,https://www.auraxis.com.br`
  - `CORS_ALLOW_CREDENTIALS=true` (não usar `*` com credenciais)
  - `CORS_ALLOWED_METHODS=GET,POST,PUT,PATCH,DELETE,OPTIONS`
  - `CORS_ALLOWED_HEADERS=Authorization,Content-Type,X-API-Contract`
  - `CORS_MAX_AGE_SECONDS=600`
- Headers de segurança por ambiente:
  - `SECURITY_X_FRAME_OPTIONS=SAMEORIGIN`
  - `SECURITY_X_CONTENT_TYPE_OPTIONS=nosniff`
  - `SECURITY_REFERRER_POLICY=strict-origin-when-cross-origin`
  - `SECURITY_PERMISSIONS_POLICY=geolocation=(), microphone=(), camera=()`
  - `SECURITY_HSTS_ENABLED=true` (produção)
  - `SECURITY_HSTS_VALUE=max-age=31536000; includeSubDomains`
- Trilha de auditoria para rotas sensíveis:
  - `AUDIT_TRAIL_ENABLED=true`
  - `AUDIT_PATH_PREFIXES=/auth/,/user/,/transactions/,/wallet,/graphql`
  - `AUDIT_PERSISTENCE_ENABLED=true` (recomendado em produção para persistência em `audit_events`)
- Proteção progressiva de login (brute-force/account takeover):
  - `LOGIN_GUARD_ENABLED=true`
  - `LOGIN_GUARD_FAILURE_THRESHOLD=5`
  - `LOGIN_GUARD_BASE_COOLDOWN_SECONDS=30`
  - `LOGIN_GUARD_MAX_COOLDOWN_SECONDS=900`
  - `LOGIN_GUARD_TRUST_PROXY_HEADERS=true` (recomendado em produção atrás de Nginx)
- Observabilidade BRAPI (contadores de integração):
  - `brapi.timeout`
  - `brapi.http_error`
  - `brapi.invalid_payload`
  - payload de snapshot disponível internamente via `build_brapi_metrics_payload()`
- Sanitização de resposta:
  - Campos sensíveis (`password`, `password_hash`, `secret*`) são removidos de payloads serializados.
  - Erros `INTERNAL_ERROR` retornam apenas `request_id` fora de DEBUG/TESTING.
  - Erros internos de execução GraphQL retornam mensagem genérica em produção.

## Situação atual de testes
Existe suíte configurada em `tests/` com `pytest` e setup isolado de banco para execução local.

## Fase 0 (documentação e consistência)
Nesta fase, o foco é alinhar documentação com comportamento real e mapear lacunas sem alterar regras de negócio já funcionando.
