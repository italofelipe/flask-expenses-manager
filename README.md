# Auraxis API

API de gestão financeira pessoal (estudo/POC com padrão de produção) construída com Flask, PostgreSQL, Redis, REST + GraphQL e pipeline forte de qualidade/segurança.

## Visão geral

O repositório entrega uma base backend pronta para evoluir produto sem virar "frankenstein":
- domínio financeiro com autenticação, transações, carteira e investimentos;
- contrato REST padronizado e camada GraphQL compartilhando o mesmo domínio;
- segurança aplicada (rate limit, hardening de headers/CORS, guard de login, auditoria);
- operação em AWS com runbook, backup, observabilidade e deploy automatizado via GitHub Actions + SSM.

## O que você vai encontrar neste repositório

### Funcionalidades implementadas
- Autenticação
  - `POST /auth/register`
  - `POST /auth/login`
  - `POST /auth/logout`
- Usuário
  - `PUT /user/profile`
  - `GET /user/me`
- Transações
  - CRUD e operações auxiliares (`restore`, `deleted`, `force delete`)
  - listagem com filtros e resumo/dashboard
- Carteira e investimentos
  - operações de carteira + valuation + histórico
- GraphQL
  - endpoint único `POST /graphql`
  - queries/mutations cobrindo fluxos principais

### Qualidade e segurança
- Linters e typing: `black`, `isort`, `flake8`, `mypy`
- Segurança: `bandit`, `gitleaks`, `pip-audit`, `trivy`, `snyk` (condicional)
- Confiabilidade: `pytest`, cobertura, `schemathesis`, mutation testing (`cosmic-ray`)
- Observabilidade e operação AWS: scripts em `scripts/` + runbooks em `docs/`

## Stack de tecnologia

### Aplicação
- Python 3.13
- Flask
- Flask-JWT-Extended
- Flask-SQLAlchemy + Flask-Migrate
- Marshmallow + Webargs
- Flask-Apispec (OpenAPI/Swagger)
- Graphene (GraphQL)
- PostgreSQL
- Redis

### Infra e operação
- Docker / Docker Compose
- Nginx + Certbot (TLS)
- AWS EC2 + SSM + Route53 + CloudWatch + SNS + S3
- GitHub Actions (CI/CD)
- SonarQube Cloud

## Arquitetura (high-level)

Estrutura principal da aplicação:
- `app/controllers/` - camada HTTP (REST/GraphQL), contrato e serialização de entrada/saída
- `app/application/` - DTOs, interfaces e serviços de aplicação
- `app/services/` - serviços de domínio e integrações
- `app/models/` - modelos SQLAlchemy
- `app/schemas/` - validação/serialização
- `app/middleware/` - auth guard, rate limit, CORS, security headers
- `app/extensions/` - inicialização de extensões e observabilidade

## Como rodar

### Pré-requisitos
- Docker + Docker Compose
- Python 3.13 (para execução local sem container e tooling)
- (Opcional) Node.js + npm para rodar suíte Postman via Newman

### 1) Ambiente DEV (recomendado para desenvolvimento)
```bash
cp .env.dev.example .env.dev
docker compose -f docker-compose.dev.yml up --build -d
```

Acessos DEV:
- API: [http://localhost:3333](http://localhost:3333)
- Health: [http://localhost:3333/healthz](http://localhost:3333/healthz)
- Swagger: [http://localhost:3333/docs/](http://localhost:3333/docs/)
- OpenAPI JSON: [http://localhost:3333/docs/swagger/](http://localhost:3333/docs/swagger/)

### 2) Ambiente PROD local/staging
```bash
cp .env.prod.example .env.prod
docker compose -f docker-compose.prod.yml up --build -d
```

### 3) Parar ambiente
```bash
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.prod.yml down
```

## Testes e validações

### Testes Python
```bash
pytest
pytest --cov=app --cov-report=term-missing --cov-report=xml
```

### Pre-commit (qualidade local)
```bash
pre-commit run --all-files
```

### Reprodução local dos checks de CI
```bash
./scripts/run_ci_quality_local.sh
./scripts/run_ci_like_actions_local.sh
```

### Suíte Postman / API Dog (smoke + regression)
Arquivos:
- coleção: `api-tests/postman/auraxis.postman_collection.json`
- environments:
  - `api-tests/postman/environments/local.postman_environment.json`
  - `api-tests/postman/environments/dev.postman_environment.json`
  - `api-tests/postman/environments/prod.postman_environment.json`

Execução:
```bash
npm install -g newman
./scripts/run_postman_suite.sh
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json
./scripts/run_postman_suite.sh ./api-tests/postman/environments/prod.postman_environment.json
```

## Deploy, operação e AWS

- Runbook principal: `docs/RUNBOOK.md`
- Planejamento de CD: `docs/CD_AUTOMATION_EXECUTION_PLAN.md`
- TLS/Nginx: `docs/NGINX_AWS_TLS.md`
- Guardrails de custo: `docs/AWS_COST_GUARDRAILS.md`
- Segredos em cloud: `docs/CLOUD_SECRETS_RUNBOOK.md`
- Plano B com RDS: `docs/RDS_PLAN_B.md`

## Documentação por tópico

### Produto, backlog e progresso
- Backlog central: `TASKS.md`
- Plano por área: `docs/PLANO_TAREFAS_POR_AREA.md`

### API e contratos
- API geral: `docs/API_DOCUMENTATION.md`
- Contrato de resposta: `docs/API_RESPONSE_CONTRACT.md`
- Schema GraphQL: `schema.graphql`
- Docs por controller: `docs/controllers/`

### Segurança
- Baseline OWASP: `docs/OWASP_S3_BASELINE.md`
- Inventário de superfície: `docs/OWASP_S3_INVENTORY.md`
- Checklist OWASP/ASVS: `docs/OWASP_S3_CHECKLIST.md`
- Plano de remediação: `docs/OWASP_S3_REMEDIATION_PLAN.md`
- Threat model STRIDE: `docs/THREAT_MODEL_STRIDE.md`

### CI/CD e qualidade
- Pipeline CI/CD: `docs/CI_CD.md`
- Plano de segurança e resiliência: `docs/CI_SECURITY_RESILIENCE_PLAN.md`
- Guia de testes: `docs/TESTING.md`

## Convenções do projeto

- Branches: padrão de nome convencional (evitar prefixos ad-hoc)
- Commits: Conventional Commits
- Qualidade mínima: sem quebrar CI/security gates
- Evolução arquitetural: incremental, retrocompatível, orientada a domínio

## Estado atual e próximos passos

- Estado de execução detalhado e histórico de progresso: `TASKS.md`
- Prioridades atuais:
  1. Consolidar CD com least-privilege por ambiente
  2. Avançar para deploy imutável por imagem (ECR)
  3. Expandir suíte externa de API (Postman/API Dog) para cenários críticos
  4. Fechar débitos de padronização de erros GraphQL e documentação OpenAPI

---
Se você acabou de chegar no projeto, comece por:
1. `README.md` (este arquivo)
2. `TASKS.md`
3. `docs/RUNBOOK.md`
4. `docs/API_DOCUMENTATION.md`
