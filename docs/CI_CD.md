# CI/CD (GitHub Actions)

Ultima atualizacao: 2026-03-19

## Objetivo

Garantir qualidade, seguranca e confiabilidade com gates obrigatorios no PR, deploy automatizado em DEV e deploy manual controlado em PROD.

## Status consolidado (checkpoint)

- Governanca (`governance.yml`) validada em modo `audit`.
- Deploy DEV/PROD validado com OIDC por ambiente.
- Workflow `AWS Security Audit` executado com sucesso (I8 concluido).
- Proximo bloco: ciclo de features (`E1 -> E2 -> E3`) mantendo os mesmos gates.

## Workflows

### 1) CI principal
Arquivo: `.github/workflows/ci.yml`

Gatilhos:
- `push` em `main`, `develop`, `master`
- `pull_request`

Jobs relevantes:
1. `quality`
- `pip-audit`, `ruff format`, `ruff check`, `mypy`, `bandit`

2. `secret-scan`
- `gitleaks` com config versionada `.gitleaks.toml`

3. `dependency-review` (somente PR)
- bloqueia vulnerabilidades novas `high+`

4. `review-signal` (somente PR, advisory)
- executa `scripts/pr_review_signal_check.py` para resumir findings do Cursor Bugbot em review threads
- modo `advisory` (nao bloqueia merge por padrao), mantendo sinal de qualidade com baixo ruido

5. `tests`
- `pytest` (sem marker schemathesis)
- cobertura minima obrigatoria `85%`

6. `ci-runtime-images`
- constroi uma vez as imagens canonicas `auraxis-ci-dev:${GITHUB_SHA}` e `auraxis-ci-prod:${GITHUB_SHA}`
- publica artifacts efemeros para reuso nos gates seguintes

7. `api-smoke`
- sobe stack local docker
- instala dependencias Node versionadas com `npm ci`
- usa `scripts/ci_stack_bootstrap.py` como bootstrap canônico
- executa o gate oficial rapido de release/pre-merge (`smoke`) via `scripts/run_postman_suite.sh`
- publica `reports/newman-smoke-report.xml`

8. `api-integration`
- sobe stack local docker isolada para a suite `full`
- usa `scripts/ci_stack_bootstrap.py` como bootstrap canônico
- executa o gate oficial dedicado de release/integracao da superficie canonica nao-privilegiada
- publica `reports/newman-full-report.xml`

9. `schemathesis`
- contrato OpenAPI com seed deterministico (`HYPOTHESIS_SEED`)
- execucao centralizada em `scripts/run_schemathesis_contract.sh`

10. `mutation`
- gate Cosmic Ray (`scripts/mutation_gate.sh`)

11. `trivy`
- scan de filesystem + imagem Docker reutilizando a imagem canonica ja construida

11. `osv-scanner` (obrigatorio)
- scan open source de lockfiles/dependencias versionadas
- usa a base `OSV.dev` como complemento ao `pip-audit` e ao `dependency-review`
- publica `reports/security/osv-results.json` como artifact

Governanca de excecoes de seguranca:
- excecoes canonicas vivem em `config/security_exception_allowlist.json`
- `pip-audit` e `OSV-Scanner` consomem a mesma fonte de verdade
- `scripts/security_exception_governance.py check` roda antes dos scans para evitar drift, ignores sem justificativa e allowlists nao rastreaveis

12. `security-evidence`
- executa `scripts/security_evidence_check.sh`

13. `pr-traceability`
- resumo advisory de merge/release traceability para PRs
- explicita se o PR e release, stacked e qual e a base/head real

14. `sonar`
- scan SonarCloud + quality gate + enforce de ratings A

Notas:
- `Cursor Bugbot` e camada complementar de review em PR.
- Bugbot nao eh gate obrigatorio no ruleset (quota/ruido), mas continua util como sinal adicional.
- O job `Review Signal (Cursor Bugbot)` publica resumo no `Step Summary` para triagem objetiva.
- `Trivy` continua responsavel por filesystem + container; `OSV-Scanner` assume a trilha open source de SCA para lockfiles/dependencias.

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

Arquitetura canonica de smoke/release gate:
- pré-merge: `ci-runtime-images` constrói a imagem uma vez e distribui artifacts efêmeros
- pré-merge: Newman roda nos jobs `api-smoke` (`smoke`) e `api-integration` (`full`) do `ci.yml`, ambos reutilizando a mesma imagem canônica
- pré-merge: smoke/full compartilham o mesmo bootstrap principal em `scripts/ci_stack_bootstrap.py`
- pré-merge: `api-smoke` tambem executa `scripts/http_latency_budget_gate.py`
- pós-deploy: smoke deterministico em Python dentro do `deploy.yml`
- fluxos legados paralelos de smoke foram removidos para evitar drift
- readiness no caminho comum de merge/release exige os dois gates oficiais (`smoke` + `full`) em verde
- o perfil `privileged` continua em workflow manual separado, fora do caminho comum

Traceability adicional:
- todo `pull_request` publica resumo advisory via `scripts/pr_traceability_check.py`
- o mesmo script pode ser usado manualmente para verificar absorcao em `master` apos merge:

```bash
python scripts/pr_traceability_check.py \
  --repo italofelipe/auraxis-api \
  --pr-number 720 \
  master-absorption
```

### Governanca de performance

- budgets canonicos vivem em `config/http_latency_budgets.json`
- o CI publica `reports/performance/http-latency-budget.json` como artifact
- o mesmo gate pode ser executado localmente com stack ja subida:

```bash
API_BASE_URL=http://localhost:3333 \
bash scripts/run_ci_like_actions_local.sh --local --with-postman
```

Politica de docs runtime:
- a documentacao publica oficial da API vive no portal `docs.auraxis.com.br/api/`
- o runtime `/docs/` e `/docs/swagger/` existe para debugging/operacao
- em `production`, a politica padrao agora e `disabled`
- a politica `public` e rejeitada em runtime seguro de producao
- se houver necessidade operacional excepcional, a exposicao deve ser explicitamente configurada como `authenticated`

### 3) Release automation
Arquivo: `.github/workflows/release-please.yml`

Fluxo:
- `push` em `master/main` dispara o `Release Please`
- a action abre ou atualiza o PR de release com changelog e versao semantica
- o PR de release precisa disparar o `CI` normal do repositório

Secret requerido:
- `RELEASE_PLEASE_TOKEN`

Notas:
- o workflow usa um token dedicado em vez de `GITHUB_TOKEN` para evitar o bloqueio anti-recursao do GitHub Actions;
- sem `RELEASE_PLEASE_TOKEN`, o workflow falha cedo com mensagem explicita em vez de criar PR de release sem checks;
- se um PR legado de release ficar preso sem statuses, um push manual na branch do release PR volta a disparar o `CI`, mas isso deve ser tratado apenas como remediation, nao como fluxo nominal.

### 4) Governance
Arquivo: `.github/workflows/governance.yml`

Fluxo:
- `mode=audit`: verifica drift do ruleset
- `mode=sync`: cria/atualiza ruleset alvo

Arquivos de suporte:
- `config/github_master_ruleset.json`
- `scripts/github_ruleset_manager.py`

Secret requerido:
- `TOKEN_GITHUB_ADMIN`

### 5) AWS Security Audit (I8)
Arquivo: `.github/workflows/aws-security-audit.yml`

Fluxo:
- `schedule` semanal (segunda) e `workflow_dispatch` manual
- assume role OIDC dedicada de auditoria (`AWS_ROLE_ARN_AUDIT`)
- executa `scripts/aws_iam_audit_i8.py`
- publica artefato `aws-iam-audit-report` (JSON)

Notas:
- Se `AWS_ROLE_ARN_AUDIT` nao estiver configurada, o workflow entra em modo `skip` sem falhar.
- Para gate estrito, use `fail_on=fail` (default) no `workflow_dispatch`.

## Pre-commit (local)

Arquivo: `.pre-commit-config.yaml`

Hooks:
- `ruff-check`, `ruff-format`
- `bandit`
- `gitleaks` com `.gitleaks.toml`
- `detect-private-key`
- `mypy`
- `sonar-local-check` (opt-in local; `enforce` em CI ou com override)
- pre-push: `security-evidence`, `pip-audit`

Governanca de excecoes:
- hooks locais usam a mesma allowlist canonica do CI
- excecao nova so entra pelo inventario versionado com `owner`, `reviewed_at` e `justification`

Política do `sonar-local-check`:
- Local (default): `AURAXIS_ENABLE_LOCAL_SONAR=false` (skip não bloqueante para evitar latência alta no fluxo diário).
- Local opt-in: `AURAXIS_ENABLE_LOCAL_SONAR=true` para executar scanner e rating checks.
- CI: `SONAR_LOCAL_MODE=enforce` automaticamente quando `CI=true`.
- Override local estrito: `AURAXIS_ENFORCE_LOCAL_SONAR=true`.

## Dependabot + auto-merge (dependências)

Arquivos:
- `.github/dependabot.yml`
- `.github/workflows/auto-merge.yml`

Política:
- auto-merge apenas para updates `patch` e `minor`;
- updates `major` exigem revisão manual;
- merge automático só conclui com checks obrigatórios da branch protection em verde.
- jobs dependentes de secrets externos devem ficar `skipped` quando o token não estiver
  disponível em PRs automatizados (ex.: Dependabot), nunca `failed`.
- no ecossistema Python do backend, updates `minor` de dependências de desenvolvimento
  não são agrupados. Ferramentas como `mypy`, `pre-commit`, `bandit`, `pip-audit`,
  `schemathesis`, `ruff` e stubs tipados devem abrir PRs individuais para isolar
  regressões de toolchain e evitar lotes com centenas de erros não atribuíveis.

## Reproducao local (CI-like)

Script oficial:
- `scripts/run_ci_like_actions_local.sh`
- Sinal de review no PR:
  - `python scripts/pr_review_signal_check.py --repo <owner/repo> --pr-number <numero> --mode advisory`
  - `python scripts/pr_review_signal_check.py --repo <owner/repo> --pr-number <numero> --mode strict`

Exemplos:
- `bash scripts/bootstrap_local_env.sh`
- `bash scripts/run_ci_like_actions_local.sh`
- `bash scripts/run_ci_like_actions_local.sh --local --with-postman`
- `bash scripts/run_ci_like_actions_local.sh --local --with-mutation`
- `npm ci && npm run smoke:local`

## Secrets e Vars esperados

Secrets:
- `SONAR_TOKEN`
- `TOKEN_GITHUB_ADMIN`

Vars:
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`
- `AWS_REGION`
- `AWS_ROLE_ARN_DEV`
- `AWS_ROLE_ARN_PROD`
- `AWS_ROLE_ARN_AUDIT` (recomendado para auditoria IAM contínua)
- `AURAXIS_DEV_INSTANCE_ID`
- `AURAXIS_PROD_INSTANCE_ID`
- opcionais: `AURAXIS_DEV_BASE_URL`, `AURAXIS_PROD_BASE_URL`

## Referencias

- `docs/RUNBOOK.md`
- `docs/CD_AUTOMATION_EXECUTION_PLAN.md`
- `TASKS.md`
