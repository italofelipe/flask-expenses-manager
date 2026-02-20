# Architecture Snapshot

## Visao geral
Auraxis API e um backend Flask com suporte a REST e GraphQL, focado em gestao financeira pessoal e planejamento de metas.

## Blocos principais
- `app/controllers/`: adapters REST por dominio.
- `app/graphql/`: schema, queries, mutations e seguranca GraphQL.
- `app/application/services/`: casos de uso e orquestracao de regra de negocio.
- `app/models/`: entidades e persistencia.
- `app/services/`: servicos de dominio/integracoes (ex.: BRAPI).
- `migrations/`: versionamento de schema (Alembic/Flask-Migrate).

## Dados e infraestrutura
- Banco principal: PostgreSQL.
- Cache/locks/rate-limit distribuido: Redis.
- Deploy: AWS EC2 com Docker Compose.
- Reverse proxy/TLS: Nginx + certificados.

## Qualidade e seguranca
- Pre-commit: black, isort, flake8, mypy, checks de seguranca.
- CI: suites de testes, gates de seguranca e policy Sonar.
- Observabilidade: metricas e logs estruturados, com runbooks em `docs/`.

## Principio arquitetural atual
Dominio centralizado com adapters REST/GraphQL finos para reduzir duplicacao e manter paridade de comportamento.
