# CI/CD (GitHub Actions)

Ultima atualizacao: 2026-02-11

## Objetivo atual
- Garantir qualidade, segurança e confiabilidade antes de merge/deploy.
- Manter deploy fora deste workflow por enquanto.

## Workflows

### 1. CI principal
Arquivo: `.github/workflows/ci.yml`

Gatilhos:
- `push` em `main`, `develop`, `master`
- `pull_request`

Jobs:
1. `quality`
- `black`, `isort`, `flake8`, `mypy`
- `pip-audit` (dependências Python)
- `bandit` (SAST, gate alto)

2. `secret-scan`
- `gitleaks` em todo histórico do checkout

3. `dependency-review` (somente PR)
- gate para novas vulnerabilidades `high+`

4. `tests`
- `pytest` com cobertura (`-m "not schemathesis"`)
- gate de cobertura mínima: `--cov-fail-under=85`
- artefatos: `coverage.xml`, `pytest-report.xml`

5. `schemathesis`
- teste de confiabilidade de contrato OpenAPI com fuzzing controlado
- usa marker `schemathesis`

6. `mutation`
- gate de mutation testing com `cosmic-ray`
- script: `scripts/mutation_gate.sh`
- configuração: `scripts/cosmic_ray.toml`

7. `trivy`
- scan de vulnerabilidades no filesystem do repo
- build da imagem prod e scan de imagem

8. `snyk` (condicional)
- só roda quando `vars.SNYK_ENABLED == 'true'`
- scan de dependências Python e de container

9. `security-evidence`
- executa `scripts/security_evidence_check.sh`
- publica `reports/security/security-evidence.md`

10. `sonar`
- scan SonarCloud + quality gate
- enforcement adicional via `scripts/sonar_enforce_ci.sh`

### 2. Recorrência
Arquivo: `.github/workflows/recurrence-job.yml`
- gera transações recorrentes por cron / execução manual

## Pre-commit (local)
Arquivo: `.pre-commit-config.yaml`

Hooks ativos:
- `black`
- `flake8`
- `isort`
- `mypy` (hook local `language: system`, executa `mypy app` no mesmo ambiente do desenvolvedor)
- `bandit` (scan `app/`, severidade alta)
- `gitleaks` (segredos em staged)
- `detect-private-key`
- `sonar-local-check`

## Reproducao local do job Quality (CI parity)
- Script oficial: `scripts/run_ci_quality_local.sh`
- Modo recomendado (paridade alta com CI):
  - `scripts/run_ci_quality_local.sh`
  - executa em container `python:3.11-slim` e roda os mesmos gates do job `Quality`.
- Modo alternativo (ambiente local ja preparado):
  - `PATH=".venv/bin:$PATH" scripts/run_ci_quality_local.sh --local`
  - roda os mesmos gates usando o ambiente local atual.

Checks executados pelo script:
- `pip-audit -r requirements.txt`
- `black --check` (arquivos Python versionados)
- `isort --check-only app tests config run.py run_without_db.py`
- `flake8 app tests config run.py run_without_db.py`
- `mypy app`
- `bandit -r app -lll -iii`

## Variáveis e secrets necessários

### Secrets
- `SONAR_TOKEN`
- `SNYK_TOKEN` (para job `snyk`)
- `RECURRENCE_DATABASE_URL`
- `RECURRENCE_SECRET_KEY`
- `RECURRENCE_JWT_SECRET_KEY`

### Variables
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`
- `SNYK_ENABLED` (`true/false`)

## Governança recomendada (fora do repo)
1. Habilitar branch protection exigindo checks obrigatórios.
2. Habilitar GitHub Secret Scanning + Push Protection.
3. Definir política de exceções de CVE (quem aprova, prazo, rastreabilidade).

## Convenções Git
- Branches: usar padrão de conventional branch (`feat/*`, `fix/*`, `chore/*`, `refactor/*`, `docs/*`, `test/*`, `ci/*`).
- Commits: seguir Conventional Commits (ex.: `feat(auth): ...`, `fix(ci): ...`, `chore(deps): ...`).
- Pull requests: título alinhado com o tipo principal de mudança quando possível.

## Referência de estratégia
- `docs/CI_SECURITY_RESILIENCE_PLAN.md`
