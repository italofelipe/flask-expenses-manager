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
1. Configure o `.env` com as variáveis mínimas:

```env
POSTGRES_DB=flaskdb
POSTGRES_USER=flaskuser
POSTGRES_PASSWORD=flaskpass
DB_HOST=db
DB_PORT=5432
```

2. Suba os containers:

```bash
docker-compose up --build
```

## Portas e acesso
- App exposto no host: `http://localhost:3333`
- Swagger UI: `http://localhost:3333/docs/`
- OpenAPI JSON: `http://localhost:3333/docs/swagger/`
- PostgreSQL: `localhost:5432`

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
- `/Users/italochagas/Desktop/projetos/flask/flask-template/docs/controllers/auth_controller.md`
- `/Users/italochagas/Desktop/projetos/flask/flask-template/docs/controllers/user_controller.md`
- `/Users/italochagas/Desktop/projetos/flask/flask-template/docs/controllers/transaction_controller.md`
- `/Users/italochagas/Desktop/projetos/flask/flask-template/docs/controllers/wallet_controller.md`
- `/Users/italochagas/Desktop/projetos/flask/flask-template/docs/API_RESPONSE_CONTRACT.md` (contrato alvo de resposta)
- `/Users/italochagas/Desktop/projetos/flask/flask-template/docs/PHASE0_RESPONSE_ADOPTION_PLAN.md` (plano de adoção sem quebra)

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
Existem testes iniciais (`tests/`), mas a cobertura ainda é baixa para o domínio completo.

## Fase 0 (documentação e consistência)
Nesta fase, o foco é alinhar documentação com comportamento real e mapear lacunas sem alterar regras de negócio já funcionando.
