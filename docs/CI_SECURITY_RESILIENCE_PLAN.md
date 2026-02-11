# CI Security & Resilience Plan

Ultima atualizacao: 2026-02-11

## Objetivo
Elevar o padrão de qualidade, resiliência e segurança do projeto com gates automáticos em pre-commit e CI.

## Avaliacao tecnica das ações propostas

### 1. Secret scanning (pre-commit + CI)
- Decisao: usar `gitleaks` (pre-commit e GitHub Actions).
- Motivo: rápido, estável e amplamente adotado.
- Complemento: `detect-private-key` no pre-commit para bloquear chaves PEM/SSH.
- Oportunidade: previne vazamento antes do push.
- Risco: falso positivo em fixtures/documentacao; mitigação por allowlist pontual e revisão de regra.

### 2. Bandit (SAST)
- Decisao: manter no CI e adicionar no pre-commit.
- Oportunidade: identifica padrões inseguros cedo.
- Risco: ruído em findings low-confidence; mitigação com triagem e ajustes graduais.

### 3. Schemathesis (confiabilidade de contrato)
- Decisao: adicionar job dedicado com escopo inicial controlado.
- Oportunidade: detecta 5xx e inconsistências de contrato com fuzzing guiado por OpenAPI.
- Risco: flakiness/performance se escopo for amplo; mitigação com `max_examples` baixo e seleção de endpoints críticos.

### 4. Mutation testing (Cosmic Ray)
- Decisao: usar `cosmic-ray` com filtro de operadores e escopo crítico de segurança.
- Oportunidade: mede efetividade real dos testes (não só cobertura).
- Risco: tempo de execução mais alto; mitigação com escopo inicial em módulos críticos e runner direcionado.

### 5. Snyk
- Decisao: integrar scan de dependências e container com gate condicional (`SNYK_ENABLED=true`).
- Oportunidade: inteligência de vuln + contexto de correção.
- Risco: requer token/licenciamento e baseline; mitigação com ativação controlada por variável.

### 6. Trivy (filesystem + imagem Docker)
- Decisao: gate sempre ativo.
- Oportunidade: visibilidade de CVEs de SO e libs no build.
- Risco: bloqueios por CVEs transitivas de base image; mitigação via atualização periódica da base e política de exceções documentada.

### 7. GitHub Secret Scanning / Push Protection
- Decisao: habilitar no GitHub (configuração de repositório/org).
- Oportunidade: defesa em profundidade no servidor.
- Risco: depende de configuração externa (não é totalmente versionável no repo).

## Plano de implementação por etapas

### Etapa A - Shift-left local (pre-commit)
1. Adicionar `gitleaks` no pre-commit.
2. Adicionar `bandit` no pre-commit.
3. Adicionar `detect-private-key` no pre-commit.

Critério de aceite:
- commit local bloqueado em segredo/chave privada/finding alto.

### Etapa B - Confiabilidade e segurança em CI
1. Job Schemathesis dedicado (OpenAPI fuzzing limitado).
2. Job Cosmic Ray com gate (módulos críticos).
3. Job Trivy para filesystem e imagem.
4. Job Snyk condicional por variável (`SNYK_ENABLED`).

Critério de aceite:
- PR só passa com todos os jobs obrigatórios verdes.

### Etapa C - Governança
1. Configurar branch protection com required checks.
2. Habilitar secret scanning + push protection no GitHub.
3. Revisar política de severidade e exceções (quando aplicável).

Critério de aceite:
- merge bloqueado sem checks e sem política explícita de exceção.

## Configuração necessária no GitHub

### Secrets
- `SONAR_TOKEN` (já em uso)
- `SNYK_TOKEN` (novo para job Snyk)

### Variables
- `SONAR_PROJECT_KEY`
- `SONAR_ORGANIZATION`
- `SNYK_ENABLED` = `true` para ativar job Snyk

## Tarefas mapeadas no backlog
- `G6`: pre-commit security hooks
- `G7`: Schemathesis
- `G8`: Cosmic Ray
- `G9`: Snyk
- `G10`: Trivy
- `G11`: branch protection + push protection
