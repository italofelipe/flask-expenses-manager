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

Resposta de sucesso:
- `201`

Erros comuns:
- `409` email já cadastrado
- `400` erro de validação

### `POST /auth/login`
Aceita `email` ou `name` + `password`.

Resposta de sucesso:
- `200` com token JWT

Erros comuns:
- `400` credenciais ausentes
- `401` credenciais inválidas

### `POST /auth/logout`
Revoga a sessão atual do usuário autenticado.

Resposta de sucesso:
- `200`

## 2) User
- `PUT /user/profile`
- `GET /user/me`

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

## 3) Transactions
- `POST /transactions`
- `PUT /transactions/{transaction_id}`
- `DELETE /transactions/{transaction_id}`
- `PATCH /transactions/restore/{transaction_id}`
- `GET /transactions/deleted`
- `DELETE /transactions/{transaction_id}/force`
- `GET /transactions/summary?month=YYYY-MM`
- `GET /transactions/list`

Contrato de resposta:
- Padrão legado (default): sem envelope `success/data/meta`.
- Novo contrato: enviar header `X-API-Contract: v2`.

### `POST /transactions`
Cria transação única ou parcelada (`is_installment=true`).

Suporta:
- tipo `income|expense`
- status (`paid|pending|cancelled|postponed|overdue`)
- recorrência (`is_recurring`, `start_date`, `end_date`)
- Com `X-API-Contract: v2`:
  - simples em `data.transaction`
  - parcelada em `data.transactions`

### `PUT /transactions/{transaction_id}`
Atualiza campos da transação.

Regra específica implementada:
- Se `status=paid`, exige `paid_at`.
- `paid_at` não pode ser no futuro.
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

### `GET /transactions/list`
Lista transações ativas do usuário.
- Com `X-API-Contract: v2`, itens em `data.transactions` e paginação em `meta.pagination`.

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
2. `GET /transactions/list` hoje retorna todos os ativos sem aplicar filtros/paginação documentados.
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
