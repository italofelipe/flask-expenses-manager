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

## Como a suíte está configurada
- `pytest.ini` define padrão de descoberta dos testes.
- `tests/conftest.py` configura um banco SQLite isolado por execução de teste.
- A aplicação usa `DATABASE_URL` quando definida (ambiente de teste),
  e mantém fallback para PostgreSQL nos demais ambientes.

## Observações
- A suíte não depende de `.env.test`.
- Cada teste roda com schema limpo (`create_all`/`drop_all`).
