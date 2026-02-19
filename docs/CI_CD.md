# CI/CD (GitHub Actions)

Ultima atualizacao: 2026-02-20

## Objetivo

Garantir qualidade, seguranca e confiabilidade com gates obrigatorios no PR, deploy automatizado em DEV e deploy manual controlado em PROD.

## Workflows

### 1) CI principal
Arquivo: `.github/workflows/ci.yml`

Gatilhos:
- `push` em `main`, `develop`, `master`
- `pull_request`

Jobs relevantes:
1. `quality`
- `pip-audit`, `black`, `isort`, `flake8`, `mypy`, `bandit`

2. `secret-scan`
- `gitleaks` com config versionada `.gitleaks.toml`

3. `dependency-review` (somente PR)
- bloqueia vulnerabilidades novas `high+`

4. `tests`
- `pytest` (sem marker schemathesis)
- cobertura minima obrigatoria `85%`

5. `api-smoke`
- sobe stack local docker
- executa suite Postman/Newman (`scripts/run_postman_suite.sh`)
- publica `reports/newman-report.xml`

6. `schemathesis`
- contrato OpenAPI com seed deterministico (`HYPOTHESIS_SEED`)
- execucao centralizada em `scripts/run_schemathesis_contract.sh`

7. `mutation`
- gate Cosmic Ray (`scripts/mutation_gate.sh`)

8. `trivy`
- scan de filesystem + imagem Docker

9. `snyk` (obrigatorio)
- scan de dependencias Python
- scan de container calibrado para reduzir ruido recorrente de base image

10. `security-evidence`
- executa `scripts/security_evidence_check.sh`

11. `sonar`
- scan SonarCloud + quality gate + enforce de ratings A

Notas:
- `Cursor Bugbot` e camada complementar de review em PR.
- Bugbot nao eh gate obrigatorio no ruleset (quota/ruido), mas continua util como sinal adicional.

### 2) Deploy
Arquivo: `.github/workflows/deploy.yml`

Fluxo:
- `push` em `master`: deploy automatico em `dev`
- `workflow_dispatch` com `env=prod`: deploy manual em `prod`

Controles:
- OIDC por ambiente (`AWS_ROLE_ARN_DEV` e `AWS_ROLE_ARN_PROD`)
- validacao de variaveis obrigatorias antes do deploy
- bloqueio de deploy PROD fora da branch `master`
- rollback automatico em falha
- smoke checks REST + GraphQL pos-deploy via `scripts/http_smoke_check.py`

### 3) Governance
Arquivo: `.github/workflows/governance.yml`

Fluxo:
- `mode=audit`: verifica drift do ruleset
- `mode=sync`: cria/atualiza ruleset alvo

Arquivos de suporte:
- `config/github_master_ruleset.json`
- `scripts/github_ruleset_manager.py`

Secret requerido:
- `TOKEN_GITHUB_ADMIN`

## Pre-commit (local)

Arquivo: `.pre-commit-config.yaml`

Hooks:
- `black`, `flake8`, `isort`
- `bandit`
- `gitleaks` com `.gitleaks.toml`
- `detect-private-key`
- `mypy`
- `sonar-local-check`
- pre-push: `security-evidence`, `pip-audit`

## Reproducao local (CI-like)

Script oficial:
- `scripts/run_ci_like_actions_local.sh`

Exemplos:
- `bash scripts/run_ci_like_actions_local.sh`
- `bash scripts/run_ci_like_actions_local.sh --local --with-postman`
- `bash scripts/run_ci_like_actions_local.sh --local --with-mutation`

## Secrets e Vars esperados

Secrets:
- `SONAR_TOKEN`
- `SNYK_TOKEN`
- `TOKEN_GITHUB_ADMIN`

Vars:
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`
- `AWS_REGION`
- `AWS_ROLE_ARN_DEV`
- `AWS_ROLE_ARN_PROD`
- `AURAXIS_DEV_INSTANCE_ID`
- `AURAXIS_PROD_INSTANCE_ID`
- opcionais: `AURAXIS_DEV_BASE_URL`, `AURAXIS_PROD_BASE_URL`

## Referencias

- `docs/RUNBOOK.md`
- `docs/CD_AUTOMATION_EXECUTION_PLAN.md`
- `TASKS.md`
