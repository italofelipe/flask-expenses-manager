# CI/CD (GitHub Actions)

## Objetivo atual
- CI de qualidade e testes.
- Análise estática no SonarQube Cloud.
- Sem etapa de deploy por enquanto.

## Workflow
Arquivo:
- `/opt/auraxis/.github/workflows/ci.yml`
- `/opt/auraxis/.github/workflows/recurrence-job.yml`

Jobs:
1. `quality`
- `black --check .`
- `isort --check-only .`
- `flake8 .`
- `mypy app`
- `pip-audit -r requirements.txt`
- `bandit -r app -lll -iii` (SAST com gate para severidade alta)

Dependências instaladas no job:
- `requirements.txt`
- `requirements-dev.txt`
- `pip-audit`
- `bandit`

2. `tests`
- `pytest --cov=app --cov-report=xml --cov-report=term-missing --junitxml=pytest-report.xml`
- publica artefatos: `coverage.xml`, `pytest-report.xml`

3. `secret-scan`
- varredura de segredos com `gitleaks/gitleaks-action`
- falha o pipeline quando encontra segredo exposto

4. `dependency-review`
- executa em `pull_request`
- usa `actions/dependency-review-action`
- gate: falha se encontrar vulnerabilidade nova com severidade `high` (ou maior)

5. `security-evidence`
- executa `scripts/security_evidence_check.sh`
- gera relatório de evidências OWASP S3
- publica artefato: `reports/security/security-evidence.md`

6. `sonar`
- executa scan no SonarQube Cloud usando `coverage.xml`
- roda apenas se as variáveis/secrets obrigatórias existirem
- após o quality gate, aplica política rígida via script:
  - ratings `security`, `reliability`, `maintainability` devem ser `A`
  - `bugs` abertos devem ser `0`
  - `vulnerabilities` abertas devem ser `0`
  - issues `CRITICAL/BLOCKER` abertas devem ser `0`

7. `generate-recurring-transactions` (workflow separado)
- workflow: `recurrence-job.yml`
- executa script `scripts/generate_recurring_transactions.py`
- gatilhos:
  - diário via `cron` (`0 3 * * *`)
  - manual via `workflow_dispatch`
- se `RECURRENCE_DATABASE_URL` não estiver configurado, job é ignorado sem falha

## Gatilhos
- `push` em `main` e `develop`
- `pull_request`

## Variáveis/Secrets necessários
No repositório do GitHub:

### Secrets
- `SONAR_TOKEN`
- `RECURRENCE_DATABASE_URL`
- `RECURRENCE_SECRET_KEY`
- `RECURRENCE_JWT_SECRET_KEY`

### Repository Variables
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`

## Dependabot
- Arquivo: `/opt/auraxis/.github/dependabot.yml`
- Atualizações semanais para:
  - dependências Python (`pip`)
  - GitHub Actions
- PRs recebem labels `dependencies` e `security`.

## Validação local de Sonar (antes do commit)
- Script: `/opt/auraxis/scripts/sonar_local_check.sh`
- Hook integrado no pre-commit: `sonar-local-check`
- Comportamento:
1. roda testes com cobertura (`coverage.xml`);
2. roda `sonar-scanner` aguardando quality gate;
3. consulta métricas no Sonar e falha se qualquer rating estiver abaixo de `A`:
   - `security_rating`
   - `reliability_rating`
   - `sqale_rating` (maintainability)

Variáveis necessárias no ambiente local:
- `SONAR_TOKEN`
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`
- opcional: `SONAR_HOST_URL` (default: `https://sonarcloud.io`)

## Hardening de runtime validado no CI
- `MAX_REQUEST_BYTES` para limitar payload global (DoS guard).
- `SECURITY_ENFORCE_STRONG_SECRETS=true` em produção para bloquear startup inseguro.
- `CORS_ALLOWED_ORIGINS` com allowlist por ambiente.
- `GRAPHQL_ALLOW_INTROSPECTION=false` em produção por padrão.
- `RATE_LIMIT_BACKEND=redis` + `RATE_LIMIT_REDIS_URL` para modo distribuído em multi-instância.
- observabilidade de rate-limit via métricas internas `rate_limit.*` e logs estruturados de backend.
- retenção de auditoria com `AUDIT_RETENTION_DAYS` + `AUDIT_RETENTION_SWEEP_INTERVAL_SECONDS`.

Comando manual:
```bash
scripts/sonar_local_check.sh
```

Validação no CI:
- Script: `/opt/auraxis/scripts/sonar_enforce_ci.sh`
- É executado no job `sonar` após o Quality Gate.
- O job falha automaticamente se qualquer regra de política não for atendida.

Validação de evidências de segurança:
- Script: `/opt/auraxis/scripts/security_evidence_check.sh`
- Job CI: `security-evidence`
- Artefato gerado: `reports/security/security-evidence.md`
- Inclui checks de baseline para:
  - guard de profundidade GraphQL
  - guard de complexidade GraphQL

## Observações
- A suíte de testes usa SQLite em execução de teste (via `tests/conftest.py`).
- Se as variáveis do Sonar não estiverem configuradas, os jobs `quality` e `tests` continuam executando normalmente.
- O arquivo `sonar-project.properties` define as convenções-base do scanner.
- O gate de `dependency-review` só roda em PR e complementa o `pip-audit` do job `quality`.
- Runbooks operacionais:
  - `/opt/auraxis/docs/RATE_LIMIT_REDIS_RUNBOOK.md`
  - `/opt/auraxis/docs/AUDIT_TRAIL_RUNBOOK.md`

## Evolução recomendada (próximos passos)
1. Adicionar proteção de branch exigindo status checks (`quality`, `secret-scan`, `dependency-review`, `tests`, `sonar`).
2. Incluir gate de cobertura mínima no pytest/CI.
3. Criar workflow de CD separado quando houver ambiente de deploy.
