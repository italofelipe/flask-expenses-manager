# Testes

## Pré-requisitos
- Python 3.13+

## Setup local
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Rodar suíte completa
```bash
pytest
```

## Rodar arquivo específico
```bash
pytest tests/test_response_contract.py
```

## Suíte Postman / API Dog (Smoke + Regression)

Coleção versionada:
- `api-tests/postman/auraxis.postman_collection.json`

Environments:
- `api-tests/postman/environments/local.postman_environment.json`
- `api-tests/postman/environments/dev.postman_environment.json`
- `api-tests/postman/environments/prod.postman_environment.json`

Runner local (Newman):
```bash
./scripts/run_postman_suite.sh
```

Runner com environment específico:
```bash
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json
./scripts/run_postman_suite.sh ./api-tests/postman/environments/prod.postman_environment.json
```

Pré-requisito:
```bash
npm install -g newman
```

Cobertura inicial da coleção:
- `GET /healthz`
- `POST /auth/register`
- `POST /auth/login`
- `GET /user/me` (autenticado)
- `POST /graphql` login inválido (garante erro público seguro)
- `POST /graphql` query `me` (autenticado)

## Como a suíte está configurada
- `pytest.ini` define padrão de descoberta dos testes.
- `tests/conftest.py` configura um banco SQLite isolado por execução de teste.
- `tests/conftest.py` isola variáveis de ambiente por teste e restaura o estado original ao final.
- A aplicação usa `DATABASE_URL` quando definida (ambiente de teste),
  e mantém fallback para PostgreSQL nos demais ambientes.

## Observações
- A suíte não depende de `.env.test`.
- Cada teste roda com schema limpo (`create_all`/`drop_all`).
- Ao final de cada teste, a sessão SQLAlchemy é removida, o engine é `dispose()` e o arquivo SQLite temporário é limpo.
