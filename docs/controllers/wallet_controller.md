# wallet_controller.py

Arquivo: `/Users/italochagas/Desktop/projetos/flask/flask-template/app/controllers/wallet_controller.py`

## Responsabilidade
Gerenciar carteira de investimentos do usuário:
- cadastro de item com ticker ou valor fixo
- listagem paginada
- atualização com trilha de histórico
- registro e listagem de operações (`buy`/`sell`)
- exclusão

## Blueprint
- Prefixo: `/wallet`
- Header opcional de contrato: `X-API-Contract: v2`

## Recursos e comportamento

## `add_wallet_entry`
Endpoint: `POST /wallet`

O que faz:
- Exige JWT.
- Valida payload com `WalletSchema`.
- Calcula `estimated_value_on_create_date` via `InvestmentService`.
- Salva item da carteira.
- Ajusta payload de saída para ocultar campos incompatíveis conforme tipo de registro.

Regras de validação efetivas:
- Com `ticker`:
  - `quantity` obrigatório
  - `value` proibido
- Sem `ticker`:
  - `value` obrigatório

Contrato de resposta:
- Default: legado (`message`, `investment`, `error`).
- `X-API-Contract: v2`: envelope padronizado (`success`, `message`, `data`, `error`, `meta`).

## `list_wallet_entries`
Endpoint: `GET /wallet`

O que faz:
- Lista itens do usuário com paginação (`page`, `per_page`).
- Ordena por `created_at desc`.
- Ajusta payload de saída omitindo campos por tipo.

Contrato v2:
- `data.items`
- `meta.pagination` com `total`, `page`, `per_page`, `pages`.

## `get_wallet_history`
Endpoint: `GET /wallet/{investment_id}/history`

O que faz:
- Verifica existência e autorização do investimento.
- Lê histórico JSON (`history`) da entidade.
- Ordena e pagina resultado.

Contrato v2:
- `data.items`
- `meta.pagination` com `total`, `page`, `per_page`, `has_next_page`.

## `update_wallet_entry`
Endpoint: `PUT /wallet/{investment_id}`

O que faz:
- Verifica autorização do usuário.
- Valida payload parcial com `WalletSchema(partial=True)`.
- Detecta mudança de `quantity` ou `value` e registra snapshot em `history`.
- Recalcula `estimated_value_on_create_date` com `InvestmentService`.
- Persiste alterações.

Contrato v2:
- sucesso em `data.investment`
- erro com `error.code` sem quebrar contrato legado default.

## `add_investment_operation`
Endpoint: `POST /wallet/{investment_id}/operations`

O que faz:
- Verifica se o investimento existe e pertence ao usuário autenticado.
- Valida payload com `InvestmentOperationSchema`.
- Persiste operação (`buy`/`sell`) vinculada ao investimento.

Campos aceitos:
- `operation_type`: `buy` ou `sell`
- `quantity`
- `unit_price`
- `fees` (opcional)
- `executed_at` (opcional, default data atual)
- `notes` (opcional)

Contrato v2:
- sucesso em `data.operation`
- erro em `error.code`.

## `list_investment_operations`
Endpoint: `GET /wallet/{investment_id}/operations`

O que faz:
- Verifica se o investimento existe e pertence ao usuário.
- Lista operações paginadas por `executed_at desc`.

Contrato v2:
- `data.items`
- `meta.pagination` com `total`, `page`, `per_page`, `pages`.

## `delete_wallet_entry`
Endpoint: `DELETE /wallet/{investment_id}`

O que faz:
- Verifica propriedade do recurso.
- Remove registro da carteira.

Contrato v2:
- sucesso/erro no envelope padronizado.

## Dependências principais
- `app.models.wallet.Wallet`
- `WalletSchema`
- `InvestmentService` (integração BRAPI)
- `PaginatedResponse`
- `InvestmentOperation` / `InvestmentOperationSchema`

## Pontos incompletos / melhorias (Fase 0)
1. Histórico é armazenado como JSON mutável na própria linha, sem versionamento formal por tabela.
2. Integração BRAPI não usa timeout explícito, retry/backoff ou cache local.
3. Campo `quantity` no model é inteiro, o que pode limitar ativos fracionários em alguns cenários.
4. Não há endpoint consolidado de valuation atual da carteira com P/L por ativo.
5. Existem logs de erro via `print`, sem estratégia padronizada de observabilidade.

## Recomendação de implementação futura (sem alterar comportamento agora)
- Criar serviços separados:
  - `WalletService` (CRUD)
  - `MarketDataService` (BRAPI, cache, retry, timeout)
  - `PortfolioValuationService` (cálculos e métricas)
- Introduzir testes de integração com mocks de BRAPI.
- Evoluir histórico para modelo de eventos/auditoria separado quando necessário.
