# graphql_controller.py

Arquivo: `/opt/auraxis/app/controllers/graphql_controller.py`

## Responsabilidade
- Expor endpoint GraphQL unificado da aplicação.
- Executar schema GraphQL e retornar payload padrão `data/errors`.

## Blueprint
- Prefixo: `/graphql`

## Endpoints

## `POST /graphql`
O que faz:
- recebe body com:
  - `query` (obrigatório)
  - `variables` (opcional)
  - `operationName` (opcional)
- executa o schema GraphQL.
- retorna:
  - `data` quando há sucesso
  - `errors` quando há falhas de validação/execução

## Observações de segurança
- O endpoint GraphQL está liberado no `auth_guard` para permitir operações públicas
  (ex.: login/register).
- Cada resolver protegido valida token Bearer no próprio contexto.
- Para operações com recursos relacionais (ex.: `investmentId`), a autorização por ownership
  também é validada no domínio GraphQL antes da execução do serviço.

## Fase atual
- Fase 1 implementada: queries/mutations essenciais por domínio
  (`auth`, `user`, `transactions`, `wallet`, `ticker` via GraphQL, `investment_operations`).
- No domínio de investimentos, as queries atuais incluem:
  - `investmentOperations`
  - `investmentOperationSummary`
  - `investmentPosition`
  - `investmentInvestedAmount`
  - `investmentValuation`
  - `portfolioValuation`
  - `portfolioValuationHistory`
- Mutations de carteira também suportam `assetClass` e `annualRate`
  para classes de ativos de renda variável e renda fixa.
- Hardening de GraphQL (complexity/depth/rate-limit específico) permanece no backlog.
