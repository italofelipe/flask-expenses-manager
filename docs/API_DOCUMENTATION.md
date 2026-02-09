# API Documentation (As-Is)

Este documento descreve o comportamento real da API com base no código atual da branch.

## Base URL
- Local (Docker): `http://localhost:3333`

## Autenticação
A API usa JWT via header:

```http
Authorization: Bearer <token>
```

Fluxo atual:
1. `POST /auth/register`
2. `POST /auth/login`
3. `POST /auth/logout`

## Domínios disponíveis
- Autenticação
- Usuário/perfil
- Transações
- Carteira (investimentos)

## Endpoints

## 1) Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`

### `POST /auth/register`
Cria usuário com `name`, `email`, `password`.

Contrato de resposta:
- Padrão legado (default): sem envelope `success/data/meta`.
- Novo contrato: enviar header `X-API-Contract: v2`.

Resposta de sucesso:
- `201`
- Com `X-API-Contract: v2`, retorna envelope padronizado e usuário em `data.user`.

Erros comuns:
- `409` email já cadastrado
- `400` erro de validação
- Em `v2`, erros retornam `error.code` semântico (`CONFLICT`, `VALIDATION_ERROR`).

### `POST /auth/login`
Aceita `email` ou `name` + `password`.

Contrato de resposta:
- Padrão legado (default): sem envelope `success/data/meta`.
- Novo contrato: enviar header `X-API-Contract: v2`.

Resposta de sucesso:
- `200` com token JWT
- Com `X-API-Contract: v2`, token fica em `data.token` e usuário em `data.user`.

Erros comuns:
- `400` credenciais ausentes
- `401` credenciais inválidas
- Em `v2`, erros retornam `error.code` (`VALIDATION_ERROR`, `UNAUTHORIZED`).

### `POST /auth/logout`
Revoga a sessão atual do usuário autenticado.

Contrato de resposta:
- Padrão legado (default): `{"message": "Logout successful"}`.
- Novo contrato: enviar header `X-API-Contract: v2`.

Resposta de sucesso:
- `200`
- Com `X-API-Contract: v2`, retorna envelope padronizado.

## 2) User
- `PUT /user/profile`
- `GET /user/me`

Contrato de resposta:
- Padrão legado (default): sem envelope `success/data/meta`.
- Novo contrato: enviar header `X-API-Contract: v2`.

### `PUT /user/profile`
Atualiza perfil financeiro/pessoal do usuário autenticado.

Campos suportados:
- `gender`
- `birth_date`
- `monthly_income`
- `net_worth`
- `monthly_expenses`
- `initial_investment`
- `monthly_investment`
- `investment_goal_date`

Resposta de sucesso:
- `200`
- Com `X-API-Contract: v2`, retorna envelope padronizado e perfil em `data.user`.

Erros comuns:
- `400` validação
- `401` token revogado/ausente
- `404` usuário não encontrado

### `GET /user/me`
Retorna:
- dados do usuário
- transações paginadas
- carteira do usuário

Query params atuais:
- `page`
- `limit`
- `status`
- `month` (`YYYY-MM`)
- Com `X-API-Contract: v2`, retorna envelope padronizado e paginação em `meta.pagination`.

## 3) Transactions
- `POST /transactions`
- `PUT /transactions/{transaction_id}`
- `DELETE /transactions/{transaction_id}`
- `PATCH /transactions/restore/{transaction_id}`
- `GET /transactions/deleted`
- `DELETE /transactions/{transaction_id}/force`
- `GET /transactions/summary?month=YYYY-MM`
- `GET /transactions/dashboard?month=YYYY-MM`
- `GET /transactions/list`
- `GET /transactions/expenses`

Contrato de resposta:
- Padrão legado (default): sem envelope `success/data/meta`.
- Novo contrato: enviar header `X-API-Contract: v2`.

### `POST /transactions`
Cria transação única ou parcelada (`is_installment=true`).

Suporta:
- tipo `income|expense`
- status (`paid|pending|cancelled|postponed|overdue`)
- recorrência (`is_recurring`, `start_date`, `end_date`)
- parcelamento com soma exata (diferença de arredondamento ajustada na última parcela)
- validações de recorrência:
  - `is_recurring=true` exige `start_date` e `end_date`
  - `due_date` deve estar entre `start_date` e `end_date`
  - `start_date` não pode ser maior que `end_date`
- Com `X-API-Contract: v2`:
  - simples em `data.transaction`
  - parcelada em `data.transactions`

### `PUT /transactions/{transaction_id}`
Atualiza campos da transação.

Regra específica implementada:
- Se `status=paid`, exige `paid_at`.
- `paid_at` não pode ser no futuro.
- Recorrência mantém consistência de intervalo (`start_date <= end_date`) e de `due_date` dentro do período quando `is_recurring=true`.
- Com `X-API-Contract: v2`, retorna envelope padronizado.

### `DELETE /transactions/{transaction_id}`
Soft delete (`deleted=true`).
- Com `X-API-Contract: v2`, retorna envelope padronizado.

### `PATCH /transactions/restore/{transaction_id}`
Restaura transação soft-deleted.
- Com `X-API-Contract: v2`, retorna envelope padronizado.

### `GET /transactions/deleted`
Lista transações deletadas logicamente do usuário.
- Com `X-API-Contract: v2`, itens em `data.deleted_transactions`.

### `DELETE /transactions/{transaction_id}/force`
Remove definitivamente uma transação já soft-deleted.
- Com `X-API-Contract: v2`, retorna envelope padronizado.

### `GET /transactions/summary?month=YYYY-MM`
Calcula total mensal de receitas e despesas e retorna transações do mês.
- Com `X-API-Contract: v2`, itens em `data.items` e paginação em `meta.pagination`.

### `GET /transactions/dashboard?month=YYYY-MM`
Retorna um dashboard mensal consolidado com foco em visão executiva:
- totais de receita, despesa e saldo (`income_total`, `expense_total`, `balance`)
- contagens por tipo (`income`, `expense`) e total
- contagens por status (`paid`, `pending`, `cancelled`, `postponed`, `overdue`)
- principais categorias (tags) de receita e despesa por valor agregado

Com `X-API-Contract: v2`:
- mês em `data.month`
- totais em `data.totals`
- contagens em `data.counts`
- categorias em `data.top_categories`

### `GET /transactions/list`
Lista transações ativas do usuário.
- Query params suportados:
  - `page`, `per_page`
  - `type` (`income|expense`)
  - `status` (`paid|pending|cancelled|postponed|overdue`)
  - `start_date`, `end_date` (`YYYY-MM-DD`, aplicados em `due_date`)
  - `tag_id`, `account_id`, `credit_card_id` (UUID)
- Com `X-API-Contract: v2`, itens em `data.transactions` e paginação em `meta.pagination`.

### `GET /transactions/expenses`
Lista despesas por período (`due_date`) com métricas agregadas do período.

Regras:
- É obrigatório enviar ao menos um parâmetro: `startDate` ou `finalDate`.
- `startDate` e `finalDate` usam formato `YYYY-MM-DD`.
- Se ambos forem enviados, `startDate` não pode ser maior que `finalDate`.

Query params suportados:
- `startDate`
- `finalDate`
- `page`, `per_page`
- `order_by` (`due_date|created_at|amount|title`)
- `order` (`asc|desc`)

Resposta inclui:
- lista paginada de despesas
- contagem total de transações do período
- contagem de receitas do período
- contagem de despesas do período
- Com `X-API-Contract: v2`:
  - despesas em `data.expenses`
  - contadores em `data.counts`
  - paginação em `meta.pagination`

## 4) Wallet
- `POST /wallet`
- `GET /wallet`
- `GET /wallet/{investment_id}/history`
- `PUT /wallet/{investment_id}`
- `DELETE /wallet/{investment_id}`

Contrato de resposta:
- Padrão legado (default): sem envelope `success/data/meta`.
- Novo contrato: enviar header `X-API-Contract: v2`.

### `POST /wallet`
Cria item da carteira.

Regras implementadas:
- Com `ticker`: `quantity` obrigatório e `value` não deve ser enviado.
- Sem `ticker`: `value` obrigatório.
- `estimated_value_on_create_date` é calculado via BRAPI (quando há ticker) ou por `value * quantity`.
- Com header `X-API-Contract: v2`, retorna envelope padronizado.

### `GET /wallet`
Lista carteira paginada (`page`, `per_page`).
- Com `X-API-Contract: v2`, paginação vem em `meta.pagination`.

### `GET /wallet/{investment_id}/history`
Retorna histórico paginado de alterações do investimento.
- Com `X-API-Contract: v2`, itens ficam em `data.items`.

### `PUT /wallet/{investment_id}`
Atualiza item da carteira e salva histórico quando `quantity` ou `value` mudam.
- Com `X-API-Contract: v2`, retorna envelope padronizado.

## 5) GraphQL (fase 1)
- `POST /graphql`
- `GET /graphql` (health/check simples)

Objetivo da fase 1:
- adicionar suporte GraphQL gradual sem quebrar os endpoints REST.
- cobrir operações essenciais por domínio.

Queries iniciais:
- `me`
- `transactions`
- `transactionSummary`
- `transactionDashboard`
- `walletEntries`
- `walletHistory`
- `tickers`

Mutations iniciais:
- `registerUser`
- `login`
- `logout`
- `updateUserProfile`
- `createTransaction`
- `deleteTransaction`
- `addWalletEntry`
- `updateWalletEntry`
- `deleteWalletEntry`
- `addTicker`
- `deleteTicker`

Autenticação:
- operações protegidas usam `Authorization: Bearer <JWT>`.
- `registerUser` e `login` são públicas.

### `DELETE /wallet/{investment_id}`
Remove item da carteira.
- Com `X-API-Contract: v2`, retorna envelope padronizado.

## Contratos e status code
A API ainda não está 100% padronizada em payload de sucesso/erro entre todos os controllers.

Referência de padronização (Fase 0):
- `/Users/italochagas/Desktop/projetos/flask/flask-template/docs/API_RESPONSE_CONTRACT.md`
- `/Users/italochagas/Desktop/projetos/flask/flask-template/docs/PHASE0_RESPONSE_ADOPTION_PLAN.md`

## Lacunas e TODOs identificados no código (Fase 0)
1. `transaction_controller.py` contém comentário TODO de enum para status/tipo, mas enums já existem no model e o TODO está desatualizado.
2. Geração de recorrência foi implementada em serviço/script e com job agendado no GitHub Actions (`.github/workflows/recurrence-job.yml`), dependente de secrets para conexão no banco.
3. Não há módulo de metas financeiras implementado (`goals`).
4. Não há CRUD exposto para `Tag`, `Account` e `CreditCard` (existem model/schema, mas sem controller).
5. A documentação histórica citava endpoints `/ticker` e `/transaction`; o código atual usa `/wallet` e `/transactions`.
6. Projeto usa Marshmallow/Webargs em runtime; Pydantic não está implementado no fluxo atual.

## Diretrizes para próximas implementações (senior baseline)
- SOLID e separação clara entre Controller, Service e regras de domínio.
- Controller fino, com regras em serviços puros e testáveis.
- Validação centralizada e consistente de contratos de entrada/saída.
- Padronização de erros e códigos HTTP.
- Cobertura de testes por domínio (unitário + integração).
- Dependências externas (BRAPI) com timeout, retry e fallback.
