# transaction_controller.py

Arquivo: `/Users/italochagas/Desktop/projetos/flask/flask-template/app/controllers/transaction_controller.py`

## Responsabilidade
Gerenciar ciclo completo de transações financeiras:
- criação (simples e parcelada)
- atualização
- soft delete e restore
- hard delete
- listagens
- resumo mensal

## Blueprint
- Prefixo: `/transactions`

## Helper

## `serialize_transaction(transaction)`
O que faz:
- Converte entidade `Transaction` em dicionário serializável para resposta HTTP.

## Contrato de resposta
- Header opcional: `X-API-Contract: v2`
- Sem header: mantém payload legado atual.
- Com `v2`: retorna envelope padronizado (`success`, `message`, `data`, `error`, `meta`).
- Helper interno de compatibilidade:
  - `_compat_success(...)`
  - `_compat_error(...)`

## Recursos e comportamento

## `TransactionResource.post`
Endpoint: `POST /transactions`

O que faz:
- Exige JWT válido e não revogado.
- Cria transação simples.
- Quando `is_installment=true`, gera múltiplas transações com `installment_group_id`.

Resposta:
- `201` (simples ou parcelada)
- `500` em erro de persistência
- Contrato v2:
  - simples: `data.transaction`
  - parcelada: `data.transactions`

## `TransactionResource.put`
Endpoint: `PUT /transactions/{transaction_id}`

O que faz:
- Exige JWT válido e autorização por dono da transação.
- Atualiza campos recebidos no payload.
- Regras implementadas:
  - `status=paid` exige `paid_at`
  - `paid_at` só pode existir com `status=paid`
  - `paid_at` não pode ser futuro
- Contrato v2:
  - sucesso em `data.transaction`
  - erros com `error.code` (`VALIDATION_ERROR`, `FORBIDDEN`, `NOT_FOUND`)

## `TransactionResource.delete`
Endpoint: `DELETE /transactions/{transaction_id}`

O que faz:
- Soft delete (`deleted = True`) da transação do usuário.
- Contrato v2:
  - sucesso com envelope padrão e `data` vazio.

## `TransactionResource.patch`
Endpoint: `PATCH /transactions/restore/{transaction_id}`

O que faz:
- Restaura transação soft-deleted (`deleted = False`).
- Contrato v2:
  - sucesso com envelope padrão e `data` vazio.

## `TransactionResource.get_deleted`
Endpoint: `GET /transactions/deleted`

O que faz:
- Lista transações marcadas como deletadas do usuário autenticado.
- Contrato v2:
  - itens em `data.deleted_transactions`
  - total em `meta.total`

## `TransactionResource.get_active`
Endpoint: `GET /transactions/list`

O que faz hoje:
- Retorna transações não deletadas do usuário.
- Ponto atual:
  - ainda não aplica filtros reais/paginação de banco apesar de documentar filtros.
- Contrato v2:
  - itens em `data.transactions`
  - paginação em `meta.pagination`

## `TransactionSummaryResource.get`
Endpoint: `GET /transactions/summary?month=YYYY-MM`

O que faz:
- Busca transações do mês e calcula totais:
  - `income_total`
  - `expense_total`
- Retorna também lista paginada no payload.
- Contrato v2:
  - dados em `data.month`, `data.income_total`, `data.expense_total`, `data.items`
  - paginação em `meta.pagination`

## `TransactionForceDeleteResource.delete`
Endpoint: `DELETE /transactions/{transaction_id}/force`

O que faz:
- Remove permanentemente transação que já esteja soft-deleted.
- Contrato v2:
  - sucesso com envelope padrão e `data` vazio.

## Dependências principais
- `app.models.transaction.Transaction`
- `TransactionType`, `TransactionStatus`
- `TransactionSchema`
- `PaginatedResponse`
- JWT callbacks de revogação

## Pontos incompletos / TODOs (identificados no código)
1. `GET /transactions/list` ainda não aplica filtros/paginação reais em nível de banco.
2. Regras de recorrência existem no payload/model, mas não há geração automática de ocorrências futuras por scheduler.

## Recomendação de implementação futura (sem alterar comportamento agora)
- Extrair casos de uso para `TransactionService` com comandos explícitos (create/update/delete/restore/summary).
- Corrigir listagem ativa com filtros de query em nível de banco.
- Implementar recorrência com job idempotente (diário/mensal) e testes de não-duplicidade.
