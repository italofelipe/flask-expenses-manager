# goal controller

Pacote: `app/controllers/goal/`

## Responsabilidade
Gerenciar metas financeiras do usuario autenticado:
- CRUD de metas
- planejamento por meta
- simulacao what-if sem persistencia

## Blueprint
- Prefixo: `/goals`
- Header opcional de contrato: `X-API-Contract: v2`

## Recursos e comportamento

## `GoalCollectionResource.post`
Endpoint: `POST /goals`

O que faz:
- Exige JWT.
- Cria meta financeira.
- Retorna meta criada no contrato legado e no contrato v2.

## `GoalCollectionResource.get`
Endpoint: `GET /goals`

O que faz:
- Exige JWT.
- Lista metas do usuario com filtros e paginação.
- Query params suportados:
  - `page` (default `1`)
  - `per_page` (default `10`)
  - `status` (opcional)
- Contrato v2:
  - itens em `data.items`
  - paginacao em `meta.pagination`

## `GoalResource.get`
Endpoint: `GET /goals/{goal_id}`

O que faz:
- Exige JWT.
- Retorna uma meta especifica com validacao de ownership.

## `GoalResource.put`
Endpoint: `PUT /goals/{goal_id}`

O que faz:
- Exige JWT.
- Atualiza uma meta especifica.
- Mantem validacao de ownership e regras de dominio.

## `GoalResource.delete`
Endpoint: `DELETE /goals/{goal_id}`

O que faz:
- Exige JWT.
- Remove uma meta do usuario.

## `GoalPlanResource.get`
Endpoint: `GET /goals/{goal_id}/plan`

O que faz:
- Exige JWT.
- Calcula plano da meta (capacidade de aporte, horizonte e recomendacoes).
- Retorna `goal` + `goal_plan`.

## `GoalSimulationResource.post`
Endpoint: `POST /goals/simulate`

O que faz:
- Exige JWT.
- Executa simulacao sem persistencia de dados.
- Retorna apenas `goal_plan`.

## Dependencias principais
- `app.application.services.goal_application_service.GoalApplicationService`
- `app.services.goal_planning_service.GoalPlanningService`
- `app.models.goal.Goal`

## Observacao arquitetural
- Controllers de metas atuam como adapter fino REST.
- Regras de negocio e validacoes permanecem centralizadas na camada de aplicacao/dominio.
