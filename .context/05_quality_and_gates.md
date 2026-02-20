# Quality Gates

## Gates locais recomendados
- `black .`
- `isort app tests config run.py run_without_db.py`
- `flake8 app tests config run.py run_without_db.py`
- `mypy app`
- `pytest -m "not schemathesis" --cov=app --cov-fail-under=85`
- `pre-commit run --all-files`

## Gates de pipeline (referencia)
- Testes automatizados (REST/GraphQL).
- Sonar policy.
- Seguranca (Bandit/Gitleaks/pip-audit/Snyk conforme ambiente).
- Deploy DEV automatico e PROD com aprovacao manual.

## Definicao minima de pronto
- Regra de negocio validada por testes.
- Linters e type-check passando.
- Contrato REST/GraphQL preservado.
- Documentacao e rastreabilidade atualizadas.
