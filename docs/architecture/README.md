# Auraxis API — Architecture Diagrams

Documentação visual da arquitetura ponta a ponta do backend Auraxis.
Todos os diagramas são Mermaid e renderizam nativamente no GitHub.

## Índice

| # | Diagrama | Tipo | Descrição |
|---|----------|------|-----------|
| 01 | [System Context](01_system_context.md) | C4 L1 | Auraxis e seus atores + sistemas externos |
| 02 | [Containers](02_containers.md) | C4 L2 | API, Web, Mobile, DB, Cache, Infra AWS |
| 03 | [API Components](03_api_components.md) | C4 L3 | Blueprints REST + resolvers GraphQL + serviços |
| 04 | [Data Model](04_data_model.md) | ER | Entidades principais e relacionamentos |
| 05 | [Auth Flow](05_auth_flow.md) | Sequence | Login → JWT → refresh rotation → revogação multi-device |
| 06 | [Request Lifecycle](06_request_lifecycle.md) | Sequence | HTTP → auth middleware → controller → service → DB |
| 07 | [AWS Deployment](07_aws_deployment.md) | Deployment | EC2 + Docker Compose + RDS + ElastiCache + CloudFront |
| 08 | [CI/CD Pipeline](08_cicd_pipeline.md) | Flowchart | GitHub Actions: lint → test → sonar → oasdiff → deploy |

## Convenções

- **C4 Model** (L1–L3): escala de contexto → containers → componentes
- Diagramas gerados com [Mermaid](https://mermaid.js.org/) — sem dependências externas
- Atualizar após mudanças arquiteturais significativas (novos blueprints, novos serviços externos, mudanças de infraestrutura)
