# Quality Gates — auraxis-api

Última atualização: 2026-03-19

> Referência operacional para agentes e engenheiros. Para contexto completo de plataforma, ver `auraxis-platform/.context/25_quality_security_playbook.md`.

---

## Gates locais (antes de todo commit)

```bash
# 0. Higiene estrutural
python3 scripts/repo_hygiene_check.py

# 1. Formatação + linting + import-sort (Ruff unificado)
ruff format .
ruff check app tests config run.py run_without_db.py

# 2. Type check
mypy app

# 4. Testes + cobertura
pytest -m "not schemathesis" --cov=app --cov-fail-under=85

# 5. Todos juntos (via pre-commit — inclui Gitleaks)
pre-commit run --all-files
```

### Thresholds locais

| Gate | Threshold | Bloqueia commit? |
|:-----|:----------|:-----------------|
| `ruff format` | zero diffs | ✅ Sim |
| `ruff check` | zero warnings | ✅ Sim |
| `mypy` | zero errors (strict) | ✅ Sim |
| `repo_hygiene_check.py` | 0 arquivos acidentais do tipo `foo 2.py` | ✅ Sim |
| `pytest --cov-fail-under` | ≥ 85% | ✅ Sim |
| `bandit -lll -iii` | 0 HIGH/CRITICAL | ✅ Sim |
| `gitleaks` (pre-commit) | 0 segredos detectados | ✅ Sim |

---

## Pipeline CI

| Job | Dependências | Bloqueia merge? | Descrição |
|:----|:-------------|:----------------|:----------|
| `quality` | — | ✅ Sim | repo hygiene + ruff format + ruff check + mypy + bandit + pip-audit |
| `secret-scan` | `quality` | ✅ Sim | Gitleaks — detect --source . |
| `dependency-review` | — (PR only) | ✅ Sim (PRs) | Dependências com vulnerabilidades HIGH+ |
| `review-signal` | — (PR only) | ❌ Não (advisory) | Cursor Bugbot — sinal de revisão |
| `tests` | `quality`, `secret-scan` | ✅ Sim | pytest ≥ 85% coverage + artifacts |
| `ci-runtime-images` | `quality`, `secret-scan` | ✅ Sim | build único das imagens canônicas do CI + artifacts efêmeros para reuso |
| `api-smoke` | `tests`, `ci-runtime-images` | ✅ Sim | Newman — única smoke suite black-box pré-merge em stack local docker usando imagem já construída |
| `schemathesis` | `quality`, `secret-scan` | ✅ Sim | Contract reliability (5 exemplos/endpoint) |
| `mutation` | `tests` | ✅ Sim | Cosmic Ray — 0% survival |
| `trivy` | `tests`, `ci-runtime-images` | ✅ Sim | FS scan + image scan (HIGH+CRITICAL) consumindo a imagem canônica já construída |
| `snyk` | `tests`, `trivy` | ✅ Sim (se habilitado) | Dep scan + container scan (HIGH+) |
| `security-evidence` | `tests`, `schemathesis` | ✅ Sim | Evidências de segurança para auditoria |
| `sonar` | `tests`, `schemathesis`, `mutation`, `trivy`, `security-evidence` | ✅ Sim | Quality gate A ratings + 0 critical bugs |

### Diagrama de dependências

```
push/PR
 │
 ├─ quality ────────────────────────────────┐
 └─ secret-scan (needs: quality) ───────────┤
                                              │
 dependency-review [PR only]                  │
 review-signal [PR only, advisory]            │
                                              ▼
                               tests (needs: quality + secret-scan)
                                │         │         │
                     ci-runtime-images
                       │          │
                  api-smoke   mutation    trivy
                                              │
                                           snyk [se ENABLE_SNYK=true]
                                              │
                               schemathesis ──┤
                                              │
                               security-evidence
                                              │
                                           sonar
```

---

## Cobertura de testes

```bash
# Ver relatório de cobertura por módulo
pytest -m "not schemathesis" --cov=app --cov-report=term-missing

# Gerar XML (para SonarCloud)
pytest -m "not schemathesis" --cov=app --cov-report=xml --cov-fail-under=85
```

- Mínimo absoluto: **85%**
- Cobertura **não pode regredir** — se um PR diminuir cobertura, deve incluir novos testes
- Módulos críticos (auth, services, models) devem ter cobertura mais alta

---

## Schemathesis (contract testing)

```bash
# Rodar localmente (requer stack rodando)
bash scripts/run_schemathesis_contract.sh

# Variáveis relevantes
SCHEMATHESIS_MAX_EXAMPLES=5       # exemplos por endpoint
HYPOTHESIS_SEED=20260220           # seed para reprodutibilidade
```

- Valida todos os endpoints REST contra o schema OpenAPI
- Detecta: respostas 5xx inesperadas, violações de schema, crashes

---

## Mutation testing (Cosmic Ray)

```bash
# Rodar localmente
bash scripts/mutation_gate.sh

# Variável de threshold
MUTATION_MAX_SURVIVAL_PERCENT=0.0  # 0% de mutantes sobrevivendo
```

- Zero tolerância para mutantes sobrevivendo
- Timeout: 20 minutos no CI

---

## Container security (Trivy)

```bash
# Scan do filesystem
trivy fs . --severity HIGH,CRITICAL

# Build e scan da imagem
docker build -f Dockerfile.prod -t auraxis-local:test .
trivy image auraxis-local:test --severity HIGH,CRITICAL
```

- `--ignore-unfixed`: ignora vulnerabilidades sem fix disponível
- `--exit-code 1`: HIGH ou CRITICAL = pipeline falha

---

## SonarCloud

Configuração: `sonar-project.properties`
- Organização: `vars.SONAR_ORGANIZATION`
- Project key: `vars.SONAR_PROJECT_KEY`
- Coverage input: `coverage.xml` (gerado pelo pytest)

Quality Gate requerido:
- Ratings: A em Reliability, Security, Maintainability
- 0 bugs críticos
- 0 security hotspots abertos
- Cobertura na diff: ≥ 80%

---

## Secrets config necessários no GitHub

| Secret/Variable | Obrigatório | Descrição |
|:----------------|:------------|:----------|
| `SONAR_TOKEN` | ✅ Sim | Token SonarCloud do projeto |
| `SONAR_ORGANIZATION` | ✅ Sim (var) | Slug da organização no SonarCloud |
| `SONAR_PROJECT_KEY` | ✅ Sim (var) | Project key no SonarCloud |
| `SNYK_TOKEN` | Opcional | Habilitar com `ENABLE_SNYK=true` |
| `GITHUB_TOKEN` | Auto | Dependency review + Gitleaks |

---

## Troubleshooting

| Problema | Causa provável | Solução |
|:---------|:---------------|:--------|
| `ruff format` diff em CI | Arquivo não formatado localmente | Rodar `ruff format .` antes de commitar |
| `repo_hygiene_check` falhou | Arquivo duplicado acidental no workspace (`foo 2.py`) | Remover/renomear o artefato local antes do commit |
| `mypy` error em CI | Type annotation faltando ou errada | Rodar `mypy app` localmente |
| Coverage < 85% | Nova lógica sem teste | Escrever testes para o código adicionado |
| Gitleaks detectou segredo | Credencial em código | Remover + rotar a credencial imediatamente |
| Trivy HIGH vulnerability | Dep desatualizada | `pip-audit -r requirements.txt` para identificar |
| Schemathesis 5xx | Bug na API ou schema incorreto | Verificar o endpoint identificado |
| Sonar quality gate fail | Rating abaixo de A | Ver detalhe no painel SonarCloud |
| Cosmic Ray survivors | Lógica não coberta por assert | Adicionar asserções mais fortes nos testes |
| api-smoke falhou | Stack não inicializou ou registry público oscilou | Verificar logs: `docker compose logs web db redis`; conferir pull/build usando os mirrors `public.ecr.aws/docker/library/*` |

### Supply chain canônica da suíte

- As imagens base críticas (`python`, `postgres`, `redis`) usam os mirrors `public.ecr.aws/docker/library/*`.
- O job `ci-runtime-images` constrói uma vez as imagens `auraxis-ci-dev:${GITHUB_SHA}` e `auraxis-ci-prod:${GITHUB_SHA}`.
- `api-smoke`, `api-integration` e `trivy` baixam artifacts efêmeros e reutilizam essas imagens, evitando rebuild redundante nos gates críticos.
- `api-smoke` e `api-integration` usam `scripts/ci_stack_bootstrap.py` como bootstrap principal, com report JSON e dumps padronizados em `reports/ci-stack/*`.
- o caminho local `scripts/run_ci_like_actions_local.sh --local --with-postman` reaproveita a mesma imagem dev e o mesmo bootstrap principal do CI.
- `scripts/ci_suite_doctor.py` deve ser o primeiro passo para detectar drift operacional local antes de subir a stack.
