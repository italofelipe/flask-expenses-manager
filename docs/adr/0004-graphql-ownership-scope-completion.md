# ADR-0004: GraphQL Ownership — Completion of ADR-0002 Scope

- Status: Accepted
- Date: 2026-05-05
- Deciders: Engineering
- Related issues: #1147
- Supersedes (partially): ADR-0002 (extends scope only)

## Contexto

ADR-0002 (2026-04-15) estabeleceu que **mutations CRUD de domínio ficam deprecadas em favor
do REST canônico**. Na época foram deprecadas as mutations de Transaction, Goal, WalletEntry,
WalletInvestmentOperation e Budget.

As mutations de **Subscription** (`createCheckoutSession`, `cancelSubscription`) foram omitidas
inadvertidamente — apesar de terem endpoints REST equivalentes
(`POST /subscription/checkout`, `POST /subscription/cancel`).

## Decisão

Extender o escopo de ADR-0002 para cobrir as mutations de Subscription omitidas:

- `createCheckoutSession` → deprecated → `POST /subscription/checkout`
- `cancelSubscription` → deprecated → `POST /subscription/cancel`

## Exceções explícitas (permanecem NÃO deprecated)

| Mutation | Justificativa |
|---|---|
| Auth mutations (login, register, etc.) | Não são CRUD de domínio |
| Simulation mutations | Operações compostas sem equivalente REST natural |
| `addTicker` / `deleteTicker` | Sem endpoint REST equivalente; GraphQL é a única superfície |
| `updateNotificationPreferences` | REST já existe (`PATCH /user/notification-preferences`) — deprecar em issue separada |
| `revokeSession` / `revokeAllSessions` | Operações de segurança — avaliar REST parity separadamente |

## Estado final pós-ADR-0004

Todas as mutations com REST equivalente estão deprecadas com `deprecation_reason` explícito
apontando para o endpoint canônico. O schema GraphQL permanece válido para backward-compat
durante o ciclo mínimo de 2 sprints definido em ADR-0002.

## Consequências

- Clients que chamam `createCheckoutSession` ou `cancelSubscription` via GraphQL recebem
  deprecation warnings em ferramentas que respeitam o schema (Apollo Studio, GraphQL Inspector).
- Nenhuma breaking change imediata — mutations continuam funcionando.
- Removal ADR separado será aberto antes de remover do schema.
