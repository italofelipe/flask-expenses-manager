# app

## Objetivo
Contem o codigo principal da aplicacao Auraxis (API REST + GraphQL), regras de dominio, schemas, middleware e extensoes.

## Estrutura (alto nivel)
- `controllers/`: camada de entrada HTTP/GraphQL (adaptadores)
- `application/`: casos de uso, DTOs e contratos de aplicacao
- `services/`: regras de negocio compartilhadas e integracoes
- `models/`: entidades ORM (SQLAlchemy)
- `schemas/`: validacao/serializacao de entrada e saida
- `middleware/`: auth, rate-limit, headers e politicas cross-cutting
- `graphql/`: schema, queries, mutations e seguranca do transporte GraphQL
- `extensions/`: inicializacao e configuracao de extensoes Flask
- `exceptions/`: erros de dominio/aplicacao
- `utils/`: utilitarios internos de suporte

## Padroes obrigatorios
- Controllers finos: sem regra de negocio complexa.
- Reuso de dominio: REST e GraphQL devem apontar para o mesmo nucleo de regras.
- Validacao explicita de entrada e ownership de recurso.
- Erros publicos padronizados, sem vazamento de detalhes internos.
- Cobertura de testes para alteracoes de comportamento.

## Regras de manutencao
- Nao introduzir acoplamento entre controller e persistencia sem camada intermediaria.
- Evolucoes devem manter retrocompatibilidade quando houver contrato publico existente.
- Toda mudanca relevante deve refletir em `TASKS.md` e testes.
