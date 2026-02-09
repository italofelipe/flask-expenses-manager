# Fase 0 - Log de Implementação

## Data
- 2026-02-08

## Objetivo desta entrega
- Criar a base técnica para padronização de respostas da API.
- Configurar a suíte de testes para rodar localmente de forma previsível.

## O que foi implementado

### 1) Contrato de resposta (base técnica)
- Criado `app/utils/response_builder.py` com:
  - `success_payload(...)`
  - `error_payload(...)`
  - `json_response(...)`

### 2) Exceções semânticas da API
- Criado `app/exceptions/api_exceptions.py` com:
  - `APIError`
  - `ValidationAPIError`
  - `UnauthorizedAPIError`
  - `ForbiddenAPIError`
  - `NotFoundAPIError`
- Criado `app/exceptions/__init__.py` para exportar as exceções.

### 3) Integração no tratamento global de erros
- Atualizado `app/extensions/error_handlers.py` para:
  - tratar `APIError` no formato padrão
  - mapear `HTTPException` para códigos semânticos (`NOT_FOUND`, `UNAUTHORIZED`, etc.)
  - padronizar exceções genéricas com `INTERNAL_ERROR`

### 4) Testes da base de contrato
- Criado `tests/test_response_contract.py` cobrindo:
  - estrutura de payload de sucesso
  - estrutura de payload de erro
  - integração dos handlers globais

### 5) Configuração da suíte de testes
- Atualizado `tests/conftest.py` para:
  - usar banco SQLite isolado por teste (`tmp_path`)
  - configurar variáveis de ambiente de teste
  - criar e destruir schema automaticamente
- Adicionado `pytest.ini` com configuração padrão da suíte.
- Atualizado `config/__init__.py` para aceitar `DATABASE_URL` (sem quebrar fallback PostgreSQL).
- Atualizado `app/__init__.py` para aplicar `DATABASE_URL` em runtime na criação da app
  (evita dependência de ordem de import durante testes).

## Resultado da validação
- Execução local da suíte: `6 passed`.
- Comando utilizado: `source .venv/bin/activate && pytest`.

## Decisões de arquitetura
- Não migrar endpoints existentes nesta etapa (evita risco funcional).
- Introduzir infraestrutura reutilizável primeiro, depois migrar domínio por domínio.
- Testes com SQLite para execução rápida local e isolamento.

## Próximo passo recomendado
- Migrar endpoints de `wallet` para usar `response_builder` de forma incremental,
  mantendo compatibilidade de payload quando necessário.

## Atualização adicional (Wallet - retrocompatibilidade)
- Endpoints de `wallet` agora aceitam header opcional `X-API-Contract: v2`.
- Sem header, permanecem no contrato legado (retrocompatível).
- Com header `v2`, retornam envelope padrão (`success`, `message`, `data`, `error`, `meta`).
- Testes adicionados em `tests/test_wallet_contract.py` cobrindo:
  - criação v1 e v2
  - erro de validação v2
  - listagem v2 com `meta.pagination`
  - update + history v2

## Atualização adicional (Transactions - retrocompatibilidade)
- Endpoints de `transactions` agora aceitam header opcional `X-API-Contract: v2`.
- Sem header, permanecem no contrato legado (retrocompatível).
- Com header `v2`, retornam envelope padrão (`success`, `message`, `data`, `error`, `meta`).
- Swagger (`@doc`) atualizado para expor o header opcional em todas as rotas de transações.
- Testes adicionados em `tests/test_transaction_contract.py` cobrindo:
  - criação v1 e v2
  - listagem ativa v2 com `meta.pagination`
  - resumo mensal v2
  - erro de validação em resumo v2 (mês ausente)
  - ciclo `delete -> restore -> delete -> force` em v2

## Atualização adicional (User - retrocompatibilidade)
- Endpoints de `user` agora aceitam header opcional `X-API-Contract: v2`.
- Sem header, permanecem no contrato legado (retrocompatível).
- Com header `v2`, retornam envelope padrão (`success`, `message`, `data`, `error`, `meta`).
- Swagger (`@doc`) atualizado para expor o header opcional nas rotas:
  - `PUT /user/profile`
  - `GET /user/me`
- Testes adicionados em `tests/test_user_contract.py` cobrindo:
  - profile v1 e v2
  - erro de validação v2 no profile
  - `user/me` v1 legado
  - `user/me` v2 com `meta.pagination`
  - erro de filtro inválido em `user/me` v2

## Atualização adicional (Auth - retrocompatibilidade)
- Endpoints de `auth` agora aceitam header opcional `X-API-Contract: v2`.
- Sem header, permanecem no contrato legado (retrocompatível).
- Com header `v2`, retornam envelope padrão (`success`, `message`, `data`, `error`, `meta`).
- Swagger (`@doc`) atualizado para expor o header opcional nas rotas:
  - `POST /auth/register`
  - `POST /auth/login`
  - `POST /auth/logout`
- Handler global de validação Webargs (`handle_webargs_error`) agora também respeita contrato `v2`.
- Ajuste defensivo aplicado em `_is_v2_contract` (`auth` e `user`) para não depender de request context em testes unitários puros.
- Testes adicionados em `tests/test_auth_contract.py` cobrindo:
  - register v1 e v2
  - erro de validação no register em v2
  - login v1 e v2
  - erro de credenciais inválidas no login em v2
  - logout v2

## Atualização adicional (Transactions - filtros e paginação em `/transactions/list`)
- Endpoint `GET /transactions/list` agora aplica filtros reais em nível de banco:
  - `type`, `status`, `start_date`, `end_date`, `tag_id`, `account_id`, `credit_card_id`
- Paginação real implementada com `page` e `per_page` (defaults `1` e `10`).
- Validação de parâmetros inválidos com resposta `400` (e `VALIDATION_ERROR` no contrato v2).
- Contrato legado foi preservado (`transactions`, `total`, `page`, `per_page`).
- Contrato v2 preservado (`data.transactions` + `meta.pagination`).
- Testes adicionados em `tests/test_transaction_contract.py` cobrindo:
  - filtros combinados + paginação no v2
  - paginação no legado
  - erro de validação para status inválido no v2

## Atualização adicional (Transactions - regras de recorrência C2)
- Validação forte de recorrência adicionada no `POST /transactions`:
  - `is_recurring=true` exige `start_date` e `end_date`
  - `start_date <= end_date`
  - `due_date` deve estar dentro do intervalo
- Validação equivalente aplicada em `PUT /transactions/{transaction_id}` com merge do estado atual + payload parcial.
- Serviço idempotente criado para gerar ocorrências recorrentes faltantes:
  - `app/services/recurrence_service.py` (`RecurrenceService.generate_missing_occurrences`)
  - Script operacional: `scripts/generate_recurring_transactions.py`
- Agendamento automático configurado:
  - GitHub Actions: `.github/workflows/recurrence-job.yml`
  - Execução diária (`cron`) + disparo manual (`workflow_dispatch`)
  - Usa secrets dedicados: `RECURRENCE_DATABASE_URL`, `RECURRENCE_SECRET_KEY`, `RECURRENCE_JWT_SECRET_KEY`
- Testes adicionados:
  - `tests/test_transaction_additional.py` (validações de recorrência)
  - `tests/test_recurrence_service.py` (idempotência e cenários ignorados)

## Atualização adicional (Transactions - endpoint de despesas por período)
- Novo endpoint: `GET /transactions/expenses`
- Requisitos implementados:
  - parâmetros `startDate` e `finalDate` (ao menos um obrigatório)
  - paginação (`page`, `per_page`)
  - ordenação (`order_by`, `order`)
  - métricas agregadas no período:
    - total de transações
    - total de receitas
    - total de despesas
- Contrato legado e `v2` suportados.
- Testes adicionados em `tests/test_transaction_contract.py` cobrindo:
  - validação de parâmetros obrigatórios
  - paginação/ordenação
  - métricas de contagem
  - resposta no contrato legado

## Atualização adicional (Transactions - parcelamento com arredondamento controlado C3)
- Cálculo de parcelas refatorado para manter soma exata do valor total.
- Regra aplicada:
  - divide com arredondamento para baixo em centavos
  - diferença residual é aplicada na última parcela
- Implementação no helper interno `_build_installment_amounts(...)`.
- Testes adicionados:
  - `tests/test_transaction_installments.py`

## Atualização adicional (Transactions - dashboard mensal C4)
- Novo endpoint: `GET /transactions/dashboard?month=YYYY-MM`
- Entregas implementadas:
  - totais mensais (`income_total`, `expense_total`, `balance`)
  - contagens por tipo (`income`, `expense`, `total`)
  - contagens por status (`paid`, `pending`, `cancelled`, `postponed`, `overdue`)
  - categorias principais por valor agregado para receitas e despesas (tags)
- Contrato legado e `v2` suportados.
- Refatoração de apoio:
  - helper único para parsing/validação de mês (`_parse_month_param`)
  - `TransactionSummaryResource` passou a reutilizar o mesmo parser
  - extração de agregações para `app/services/transaction_analytics_service.py`
    (separação de responsabilidades e melhor testabilidade)
- Testes adicionados em `tests/test_transaction_contract.py`:
  - dashboard mensal no contrato `v2`
  - dashboard mensal no contrato legado
  - validação de `month` inválido
- Validação da suíte:
  - testes de transações passaram
  - suíte completa passou com cobertura total `88%`

## Atualização adicional (Qualidade - lint stack)
- Corrigido problema de execução local do `flake8` causado por incompatibilidade de `pyflakes`.
- Ajuste aplicado em `requirements-dev.txt`:
  - `pyflakes==3.2.0` (compatível com `flake8==7.1.1`)
- Validação executada:
  - `pre-commit` (black, flake8, isort, mypy) passou para os arquivos alterados.

## Atualização adicional (GraphQL - fase 1, rollout gradual)
- Base GraphQL adicionada com endpoint dedicado:
  - `GET/POST /graphql`
  - arquivos principais:
    - `app/controllers/graphql_controller.py`
    - `app/graphql/schema.py`
    - `app/graphql/auth.py`
- Suporte inicial por domínio/controller:
  - Auth: `registerUser`, `login`, `logout`
  - User: `me`, `updateUserProfile`
  - Transactions: `transactions`, `transactionSummary`, `transactionDashboard`,
    `createTransaction`, `deleteTransaction`
  - Wallet: `walletEntries`, `walletHistory`, `addWalletEntry`,
    `updateWalletEntry`, `deleteWalletEntry`
  - Ticker: `tickers`, `addTicker`, `deleteTicker`
- Compatibilidade:
  - endpoints REST permanecem inalterados.
  - GraphQL opera em paralelo com autenticação Bearer por resolver protegido.
- Observabilidade de backlog:
  - hardening de GraphQL (complexity/depth/rate-limit específico) ficou
    explicitamente planejado em `TASKS.md`.
