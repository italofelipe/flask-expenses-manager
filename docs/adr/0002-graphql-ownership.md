# ADR-0002: GraphQL Ownership — Queries somente, REST como dono do CRUD

- Status: Accepted
- Date: 2026-04-15
- Deciders: Engineering
- Related issues: #1021

## Contexto

A API Auraxis nasceu com duas superfícies paralelas: REST (Flask controllers) e GraphQL (Ariadne).
Com o tempo, mutations GraphQL foram adicionadas para CRUD de transações, metas e carteira — duplicando
a lógica de negócio já presente nos controllers REST e criando dois pontos de entrada para a mesma operação.

Problemas identificados:

1. **Duplicação de validação** — schemas Marshmallow (REST) e resolvers GraphQL implementam
   as mesmas regras de negócio de formas diferentes, gerando drift silencioso.
2. **Cobertura desigual** — testes de integração cobrem o caminho REST; o caminho GraphQL
   tem cobertura menor e contrato não documentado no OpenAPI.
3. **Autorização em dois lugares** — guards de entitlement precisam ser replicados em cada mutation
   e em cada controller REST.
4. **Custo de manutenção** — cada nova feature que toca CRUD precisa ser implementada em ambas
   as superfícies.

## Decisão

**GraphQL passa a ser somente de leitura** no escopo de mutations CRUD de domínio.

Regras derivadas:

1. **Mutations de CRUD de domínio** (Transaction, Goal, Wallet/WalletEntry) ficam **deprecated**
   com `deprecation_reason` explícito no schema GraphQL, apontando para o endpoint REST equivalente.
2. **Novas mutations GraphQL** só são permitidas para operações que não têm representação REST
   natural (ex.: subscrições, operações compostas cross-domínio sem ID canônico).
3. **Queries GraphQL continuam normalmente** — são a forma preferida para agregações complexas
   que seriam custosas em REST (ex.: dashboard com múltiplos relacionamentos em um único roundtrip).
4. **Remoção das mutations deprecated** só ocorre após ADR de remoção explícito e ciclo de
   depreciação mínimo de 2 sprints com anúncio no changelog.

## Mutations deprecadas nesta decisão

| Mutation | Substituto REST |
|---|---|
| `createTransaction` | `POST /transactions` |
| `updateTransaction` | `PATCH /transactions/{id}` |
| `deleteTransaction` | `DELETE /transactions/{id}` |
| `createGoal` | `POST /goals` |
| `updateGoal` | `PATCH /goals/{id}` |
| `deleteGoal` | `DELETE /goals/{id}` |
| `addWalletEntry` | `POST /wallet` |
| `updateWalletEntry` | `PATCH /wallet/{id}` |
| `deleteWalletEntry` | `DELETE /wallet/{id}` |

## Consequências

**Positivas:**
- Uma única fonte de verdade para validação (schemas Marshmallow).
- OpenAPI cobre 100% do contrato público.
- Autorização centralizada nos controllers REST.
- Menor surface area para testes de integração.

**Negativas:**
- Clientes que consomem mutations GraphQL precisam migrar para REST.
  Mitigação: `deprecation_reason` no schema avisa ferramentas GraphQL (ex.: Apollo Studio).
- Queries GraphQL complexas que misturam leitura com side-effects precisam de avaliação
  caso a caso antes de serem adicionadas.

## Alternativas consideradas

- **Manter ambas as superfícies em paridade** — descartado pelo custo de manutenção e
  pelo risco de drift de contrato.
- **Remover GraphQL completamente** — descartado porque queries GraphQL ainda agregam
  valor para o client web em operações de leitura complexas.
