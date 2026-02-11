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

Dependências instaladas no job:
- `requirements.txt`
- `requirements-dev.txt`

2. `tests`
- `pytest --cov=app --cov-report=xml --cov-report=term-missing --junitxml=pytest-report.xml`
- publica artefatos: `coverage.xml`, `pytest-report.xml`

3. `security-evidence`
- executa `scripts/security_evidence_check.sh`
- gera relatório de evidências OWASP S3
- publica artefato: `reports/security/security-evidence.md`

4. `sonar`
- executa scan no SonarQube Cloud usando `coverage.xml`
- roda apenas se as variáveis/secrets obrigatórias existirem
- após o quality gate, aplica política rígida via script:
  - ratings `security`, `reliability`, `maintainability` devem ser `A`
  - `bugs` abertos devem ser `0`
  - `vulnerabilities` abertas devem ser `0`
  - issues `CRITICAL/BLOCKER` abertas devem ser `0`

4. `generate-recurring-transactions` (workflow separado)
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

## Observações
- A suíte de testes usa SQLite em execução de teste (via `tests/conftest.py`).
- Se as variáveis do Sonar não estiverem configuradas, os jobs `quality` e `tests` continuam executando normalmente.
- O arquivo `sonar-project.properties` define as convenções-base do scanner.

## Evolução recomendada (próximos passos)
1. Adicionar proteção de branch exigindo status checks (`quality`, `tests`, `sonar`).
2. Incluir gate de cobertura mínima no pytest/CI.
3. Criar workflow de CD separado quando houver ambiente de deploy.
