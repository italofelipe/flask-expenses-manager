# Testes

## Pré-requisitos
- Python 3.13
- Se `python3.13` nao estiver no `PATH`, os scripts oficiais tentam resolver uma instalacao `3.13.x` do `pyenv`

## Setup local
```bash
bash scripts/bootstrap_local_env.sh
```

## Rodar suíte completa
```bash
scripts/repo_bin.sh pytest
```

## Rodar arquivo específico
```bash
scripts/repo_bin.sh pytest tests/test_response_contract.py
```

## Suite Postman / Newman (Canonica E2E + Smoke)

Coleção versionada:
- `api-tests/postman/auraxis.postman_collection.json`

Environments:
- `api-tests/postman/environments/local.postman_environment.json`
- `api-tests/postman/environments/dev.postman_environment.json`
- `api-tests/postman/environments/prod.postman_environment.json`

Bootstrap do runner:
```bash
npm ci
```

Gerar/regravar a collection oficial:
```bash
npm run postman:build
```

Runner local (Newman):
```bash
npm run postman:local
```

Perfis oficiais:
```bash
npm run postman:smoke:local
npm run postman:full:local
npm run postman:privileged:dev
```

Perfis oficiais no CI:
```bash
npm run postman:smoke:ci
npm run postman:full:ci
```

Runner com environment específico:
```bash
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json
./scripts/run_postman_suite.sh ./api-tests/postman/environments/prod.postman_environment.json
```

Runner com perfil explícito:
```bash
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json --profile smoke
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json --profile full
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json --profile privileged
```

Fluxos privilegiados opcionais:
```bash
POSTMAN_ENABLE_PRIVILEGED_FLOWS=true \
POSTMAN_ADMIN_TOKEN=<token-admin> \
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json --profile privileged
```

Cobertura canonica atual:
- Auth: register, login, logout, forgot/reset invalid token
- User: me, profile, questionnaire
- Transactions: create, update, list, summary, dashboard, expenses, due-range, delete/restore/force-delete
- Goals: create, list, get, plan, simulate, update, delete
- Wallet: create, list, update, history, valuation, operations CRUD, position, invested amount
- Simulations: installment-vs-cash calculate/save e bridges com subset privilegiado opcional
- Alerts: preferences, list, read/delete negative paths
- Subscriptions/Entitlements: subscription me, checkout/cancel, webhook invalid signature, entitlements list/check, admin routes no perfil privilegiado
- Shared entries: by-me, with-me, invitations list/create/accept/revoke negative paths
- Fiscal: csv upload/confirm, receivables list/create/receive/delete negative path, summary, fiscal documents list/create
- GraphQL: validation, auth-safe errors, me, installment-vs-cash calculate/save

Perfis da suíte:
- `smoke`: subconjunto mínimo canônico de saúde funcional cross-domain
- `full`: coleção completa REST + GraphQL não-privilegiada
- `privileged`: bootstrap mínimo + fluxos admin/privilegiados que exigem `POSTMAN_ENABLE_PRIVILEGED_FLOWS=true` e `POSTMAN_ADMIN_TOKEN`
- O CI trata `smoke` como gate oficial rápido de release/pre-merge
- O CI trata `full` como gate oficial dedicado de release/integracao com artifact separado
- readiness de merge/release exige `smoke` + `full` verdes no caminho comum
- O perfil `privileged` roda em workflow manual separado, para evitar acoplamento do CI comum a token administrativo

## Como a suíte está configurada
- `pytest.ini` define padrão de descoberta dos testes.
- `tests/conftest.py` configura um banco SQLite isolado por execução de teste.
- `tests/conftest.py` isola variáveis de ambiente por teste e restaura o estado original ao final.
- A aplicação usa `DATABASE_URL` quando definida (ambiente de teste),
  e mantém fallback para PostgreSQL nos demais ambientes.
- `tests/test_postman_collection_contract.py` trava a paridade entre a collection canônica e as rotas REST críticas do contrato.

## Observações
- A suite não depende de `.env.test`.
- Cada teste roda com schema limpo (`create_all`/`drop_all`).
- Ao final de cada teste, a sessão SQLAlchemy é removida, o engine é `dispose()` e o arquivo SQLite temporário é limpo.
- Newman e Postman sao a trilha oficial de validacao black-box da API; o smoke pós-deploy oficial continua em `scripts/http_smoke_check.py`.
- No caminho comum de CI, a evidencia oficial de release da trilha black-box e publicada como artifacts separados: `newman-smoke-report` e `newman-full-report`.
- O environment `prod` deve ser usado apenas com total consciencia de que a collection cria dados de teste reais via registro/login e recursos associados.
