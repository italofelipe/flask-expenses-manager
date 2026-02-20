# Fase 0 - Plano de Adoção do Contrato de Resposta

Referência: `/opt/auraxis/docs/API_RESPONSE_CONTRACT.md`

Este plano mapeia o estado atual por endpoint e define a migração para contrato padronizado sem mexer no funcionamento já existente.

## 1) Estado atual (as-is)

## Auth (`/auth/*`)
- Formato atual: mistura `message`, `data`, `error` sem envelope fixo.
- Status geral: parcialmente consistente.

## User (`/user/*`)
- Formato atual: em geral usa `message` + payload específico.
- Status geral: parcialmente consistente.

## Transactions (`/transactions/*`)
- Formato atual: mistura `error`/`message`, respostas variam por rota.
- Status geral: inconsistente entre recursos.

## Wallet (`/wallet/*`)
- Formato atual: retorno direto de dicts com chaves variáveis (`error`, `messages`, `investment`, etc.).
- Status geral: inconsistente.

## 2) Matriz endpoint -> gap principal
- `POST /auth/register`: hoje retorna `{message, data}`; falta `success`.
- `POST /auth/login`: hoje retorna `{message, token, user}`; falta envelope.
- `POST /auth/logout`: hoje retorna `{message}`; falta envelope.
- `PUT /user/profile`: payload grande inline; falta envelope + `meta`.
- `GET /user/me`: mistura recursos no mesmo corpo; falta envelope + `meta.pagination` unificada.
- `POST /transactions`: retornos diferentes entre simples e parcelado.
- `PUT /transactions/{id}`: usa `{message, transaction}`; falta envelope.
- `DELETE /transactions/{id}`: usa `{message}`; falta envelope.
- `PATCH /transactions/restore/{id}`: usa `{message}`; falta envelope.
- `GET /transactions/deleted`: sem envelope e sem paginação padronizada.
- `GET /transactions/list`: sem filtros reais e sem envelope.
- `GET /transactions/summary`: estrutura própria; falta envelope padrão.
- `DELETE /transactions/{id}/force`: sem envelope padrão.
- `POST /wallet`: usa `{message, investment}`; falta envelope.
- `GET /wallet`: paginação fora de `meta`.
- `GET /wallet/{id}/history`: paginação via helper sem envelope único global.
- `PUT /wallet/{id}`: usa `{message, investment}`; falta envelope.
- `DELETE /wallet/{id}`: usa `{message}`; falta envelope.

## 3) Ordem de adoção (incremental)
1. Criar utilitário de resposta (`response_builder`) sem alterar comportamento das rotas existentes.
2. Aplicar primeiro em endpoints novos.
3. Aplicar por domínio existente nesta ordem:
   1. Wallet
   2. Transactions
   3. User
   4. Auth
4. Atualizar Swagger examples ao final de cada domínio.
5. Garantir testes de contrato antes de migrar o próximo domínio.

## 4) Critérios de aceite por endpoint
- Retorna `success` e `message` sempre.
- Em sucesso, conteúdo principal dentro de `data`.
- Em erro, `error.code` e `error.details` quando aplicável.
- Paginação sob `meta.pagination`.
- Teste automatizado cobrindo formato.

## 5) Itens incompletos/TODOs do código atual que impactam a adoção
1. `GET /transactions/list` sem filtros/paginação efetiva no banco.
2. Ausência de módulo de metas (`goals`) e cadastros auxiliares (Tag/Account/CreditCard) via controller.
3. Ausência de padrão único de serialização entre controllers.

## 6) Observações de engenharia (senior baseline)
- Controller deve somente orquestrar request/response.
- Regras de domínio devem ir para serviços puros e testáveis.
- Erros de domínio devem ser mapeados para exceções semânticas e `error.code` estável.
- Evitar lógica de serialização ad-hoc por endpoint.
