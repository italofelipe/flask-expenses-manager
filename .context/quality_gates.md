# Quality Gates — auraxis-api

Última atualização: 2026-02-23

> Referência operacional para agentes e engenheiros. Para contexto completo de plataforma, ver `auraxis-platform/.context/25_quality_security_playbook.md`.

---

## Gates locais (antes de todo commit)

```bash
# 1. Formatação
black .
isort app tests config run.py run_without_db.py

# 2. Linting
flake8 app tests config run.py run_without_db.py

# 3. Type check
mypy app

# 4. Testes + cobertura
pytest -m "not schemathesis" --cov=app --cov-fail-under=85

# 5. Todos juntos (via pre-commit — inclui Gitleaks)
pre-commit run --all-files
```

### Thresholds locais

| Gate | Threshold | Bloqueia commit? |
|:-----|:----------|:-----------------|
| `black` | zero diffs | ✅ Sim |
| `isort` | zero diffs | ✅ Sim |
| `flake8` | zero warnings | ✅ Sim |
| `mypy` | zero errors (strict) | ✅ Sim |
| `pytest --cov-fail-under` | ≥ 85% | ✅ Sim |
| `bandit -lll -iii` | 0 HIGH/CRITICAL | ✅ Sim |
| `gitleaks` (pre-commit) | 0 segredos detectados | ✅ Sim |

---

## Pipeline CI — 11 jobs

| Job | Dependências | Bloqueia merge? | Descrição |
|:----|:-------------|:----------------|:----------|
| `quality` | — | ✅ Sim | black + isort + flake8 + mypy + bandit + pip-audit |
| `mypy-matrix` | — | ✅ Sim | mypy em Python 3.11 + 3.13 |
| `secret-scan` | `quality` | ✅ Sim | Gitleaks — detect --source . |
| `dependency-review` | — (PR only) | ✅ Sim (PRs) | Dependências com vulnerabilidades HIGH+ |
| `review-signal` | — (PR only) | ❌ Não (advisory) | Cursor Bugbot — sinal de revisão |
| `tests` | `quality`, `secret-scan` | ✅ Sim | pytest ≥ 85% coverage + artifacts |
| `api-smoke` | `tests` | ✅ Sim | Newman — smoke suite em local docker stack |
| `schemathesis` | `quality`, `secret-scan` | ✅ Sim | Contract reliability (5 exemplos/endpoint) |
| `mutation` | `tests` | ✅ Sim | Cosmic Ray — 0% survival |
| `trivy` | `tests` | ✅ Sim | FS scan + image scan (HIGH+CRITICAL) |
| `snyk` | `tests`, `trivy` | ✅ Sim (se habilitado) | Dep scan + container scan (HIGH+) |
| `security-evidence` | `tests`, `schemathesis` | ✅ Sim | Evidências de segurança para auditoria |
| `sonar` | `tests`, `schemathesis`, `mutation`, `trivy`, `security-evidence` | ✅ Sim | Quality gate A ratings + 0 critical bugs |

### Diagrama de dependências

```
push/PR
 │
 ├─ quality ──────────────────────────────────┐
 ├─ mypy-matrix                               │
 └─ secret-scan (needs: quality) ─────────────┤
                                              │
 dependency-review [PR only]                  │
 review-signal [PR only, advisory]            │
                                              ▼
                               tests (needs: quality + secret-scan)
                                │         │         │
                         api-smoke    mutation    trivy
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

- Mínimo absoluto: **85% global** (medido pelo CI job `tests`)
- **Cobertura de código novo ≥ 80%** — SonarCloud mede apenas os arquivos do PR; falha se < 80%
- Cobertura **não pode regredir** — se um PR diminuir cobertura, deve incluir novos testes
- Módulos críticos (auth, services, controllers) devem ter cobertura mais alta

### Regra obrigatória: todo controller deve ter teste HTTP

> Incidente B10 (2026-03-10): controller entregue com 45% de cobertura porque agente
> testou apenas a camada de service. SonarCloud bloqueou o PR com 65% de cobertura nova.

Para **todo `MethodView` Flask criado**, o agente DEVE criar um arquivo de teste em
`tests/controllers/<modulo>/test_<resource>.py` que cubra:

| Cenário | Status esperado |
|:--------|:----------------|
| Sucesso autenticado (todos os métodos HTTP da rota) | `200` / `201` |
| Sem token de autenticação | `401` |
| Payload inválido / faltando campos | `422` |
| Violação de regra de negócio (ex: count errado) | `400` |

**Padrão de auth em testes de controller (obrigatório):**

```python
import uuid

def _register_and_login(client) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"test-{suffix}@email.com"
    password = "StrongPass@123"
    r = client.post("/auth/register", json={"name": f"test-{suffix}", "email": email, "password": password})
    assert r.status_code == 201
    r2 = client.post("/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r2.get_json()["token"]

def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
```

> **NÃO EXISTE** fixture `auth_headers`, `auth_client` ou `authenticated_client` no conftest.py.
> Usar sempre `_register_and_login(client)` + `_auth(token)`.

**SQLAlchemy 2.x — padrão obrigatório:**

```python
# ❌ PROIBIDO — API legada (causa LegacyAPIWarning tratada como erro pelo pytest.ini)
user = User.query.get(user_id)

# ✅ CORRETO — SQLAlchemy 2.x
from uuid import UUID
user = db.session.get(User, UUID(str(user_id)))
```

**Verificação de cobertura de arquivo novo antes de commitar:**

```bash
# Checar cobertura somente do(s) arquivo(s) novo(s):
pytest tests/controllers/<modulo>/test_<resource>.py \
       tests/application/test_<service>.py \
       --cov=app/controllers/<modulo>/<resource>.py \
       --cov=app/application/services/<service>.py \
       --cov-report=term-missing -v
# Qualquer arquivo com < 80%: adicionar mais casos de teste antes de commitar.
```

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
| `black` diff em CI | Arquivo não formatado localmente | Rodar `black .` antes de commitar |
| `mypy` error em CI | Type annotation faltando ou errada | Rodar `mypy app` localmente |
| Coverage < 85% | Nova lógica sem teste | Escrever testes para o código adicionado |
| Gitleaks detectou segredo | Credencial em código | Remover + rotar a credencial imediatamente |
| Trivy HIGH vulnerability | Dep desatualizada | `pip-audit -r requirements.txt` para identificar |
| Schemathesis 5xx | Bug na API ou schema incorreto | Verificar o endpoint identificado |
| Sonar quality gate fail | Rating abaixo de A | Ver detalhe no painel SonarCloud |
| Cosmic Ray survivors | Lógica não coberta por assert | Adicionar asserções mais fortes nos testes |
| api-smoke falhou | Stack não inicializou | Verificar logs: `docker compose logs web db redis` |
