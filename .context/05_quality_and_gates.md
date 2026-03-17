# Quality Gates

## Gates locais recomendados

> **Linter único: Ruff.** `flake8`, `black` e `isort` foram removidos. Formatação e
> import-sort são gerenciados pelo Ruff (`[tool.ruff.lint.isort]` em `pyproject.toml`).

- `ruff format .`
- `ruff check app tests config run.py run_without_db.py`
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
