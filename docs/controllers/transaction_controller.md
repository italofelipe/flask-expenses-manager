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

## `TransactionResource.put`
Endpoint: `PUT /transactions/{transaction_id}`

O que faz:
- Exige JWT válido e autorização por dono da transação.
- Atualiza campos recebidos no payload.
- Regras implementadas:
  - `status=paid` exige `paid_at`
  - `paid_at` só pode existir com `status=paid`
  - `paid_at` não pode ser futuro

## `TransactionResource.delete`
Endpoint: `DELETE /transactions/{transaction_id}`

O que faz:
- Soft delete (`deleted = True`) da transação do usuário.

## `TransactionResource.patch`
Endpoint: `PATCH /transactions/restore/{transaction_id}`

O que faz:
- Restaura transação soft-deleted (`deleted = False`).

## `TransactionResource.get_deleted`
Endpoint: `GET /transactions/deleted`

O que faz:
- Lista transações marcadas como deletadas do usuário autenticado.

## `TransactionResource.get_active`
Endpoint: `GET /transactions/list`

O que faz hoje:
- Retorna transações não deletadas do usuário.

## `TransactionSummaryResource.get`
Endpoint: `GET /transactions/summary?month=YYYY-MM`

O que faz:
- Busca transações do mês e calcula totais:
  - `income_total`
  - `expense_total`
- Retorna também lista paginada no payload.

## `TransactionForceDeleteResource.delete`
Endpoint: `DELETE /transactions/{transaction_id}/force`

O que faz:
- Remove permanentemente transação que já esteja soft-deleted.

## Dependências principais
- `app.models.transaction.Transaction`
- `TransactionType`, `TransactionStatus`
- `TransactionSchema`
- `PaginatedResponse`
- JWT callbacks de revogação

## Pontos incompletos / TODOs (identificados no código)
1. Existe TODO explícito: `CRIAR ENUMS PARA MAPEAR OS STATUS E TIPOS DE TRANSACOES`.
2. Esse TODO está desatualizado, porque os enums já existem em `app/models/transaction.py`.
3. `GET /transactions/list` não aplica filtros e paginação descritos na documentação do próprio endpoint.
4. Regras de recorrência existem no payload/model, mas não há geração automática de ocorrências futuras por scheduler.

## Recomendação de implementação futura (sem alterar comportamento agora)
- Extrair casos de uso para `TransactionService` com comandos explícitos (create/update/delete/restore/summary).
- Corrigir listagem ativa com filtros de query em nível de banco.
- Implementar recorrência com job idempotente (diário/mensal) e testes de não-duplicidade.
