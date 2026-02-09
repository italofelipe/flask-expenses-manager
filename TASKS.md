# TASKS - Central de TODOs e Progresso

Ultima atualizacao: 2026-02-09

## Regras de uso deste arquivo
- Este arquivo centraliza TODOs de produto, engenharia e qualidade.
- Cada tarefa deve manter: `Status`, `Progresso`, `Risco`, `Commit` (quando aplicavel).
- Ao concluir uma tarefa, atualizar `Status=Done`, `Progresso=100%` e preencher `Commit`.

## Legenda de status
- `Todo`: ainda nao iniciada.
- `In Progress`: em andamento.
- `Blocked`: bloqueada por dependencia/decisao.
- `Done`: concluida e validada.

## Backlog central

| ID | Area | Tarefa | Status | Progresso | Risco | Commit | Ultima atualizacao |
|---|---|---|---|---:|---|---|---|
| A1 | API Base | Padronizar contrato de resposta (sucesso/erro) em todos os endpoints | In Progress | 70% | Medio: domínios futuros ainda nao padronizados | da2ff52, f3ef3c0 | 2026-02-09 |
| A2 | API Base | Revisar OpenAPI/Swagger para refletir rotas reais | Todo | 35% | Medio: divergencia gera erro de consumo em cliente | da19f35, f3ef3c0 | 2026-02-09 |
| A3 | API Base | Remover inconsistencias de nomenclatura (ticker/wallet/investment) | Todo | 20% | Medio: confusao entre recurso legado e atual |  | 2026-02-09 |
| A4 | API Base | Definir estrategia unica de validacao (Marshmallow vs Pydantic gradual) | Todo | 0% | Baixo: decisao arquitetural pendente |  | 2026-02-09 |
| B1 | Usuario | Criar endpoint dedicado para leitura de perfil (payload reduzido) | Todo | 0% | Baixo |  | 2026-02-09 |
| B2 | Usuario | Reforcar validacoes de coerencia financeira no perfil | Todo | 0% | Medio: dados inconsistentes impactam metas |  | 2026-02-09 |
| B3 | Usuario | Adicionar auditoria de atualizacao de perfil | Todo | 0% | Medio: rastreabilidade insuficiente |  | 2026-02-09 |
| C1 | Transacoes | Corrigir listagem de transacoes com filtros/paginacao reais no banco | Done | 100% | Baixo | 497f901 | 2026-02-09 |
| C2 | Transacoes | Regras fortes de recorrencia + geracao automatica idempotente | Done | 100% | Baixo | f3ef3c0 | 2026-02-09 |
| C3 | Transacoes | Consolidar regras de parcelamento (soma exata e arredondamento final) | Done | 100% | Baixo | 497f901 | 2026-02-09 |
| C4 | Transacoes | Criar endpoint de dashboard mensal (receitas, despesas, saldo, categorias) | Done | 100% | Baixo | pending-commit | 2026-02-09 |
| C5 | Transacoes | Endpoint de despesas por periodo com paginacao/ordenacao/metricas | Done | 100% | Baixo | f3ef3c0 | 2026-02-09 |
| D1 | Investimentos | Entidade de operacoes (`buy`/`sell`) com data, preco, quantidade, taxas | Todo | 0% | Alto: base necessaria para analytics confiavel |  | 2026-02-09 |
| D2 | Investimentos | Calculo de custo medio por ativo e posicao atual | Todo | 0% | Alto: regra financeira sensivel |  | 2026-02-09 |
| D3 | Investimentos | Calculo de quanto investiu no dia por data de operacao | Todo | 0% | Alto: depende de D1 |  | 2026-02-09 |
| D4 | Investimentos | Calculo de valor atual por ativo e consolidado (BRAPI + fallback) | Todo | 0% | Alto: dependencia externa (BRAPI) |  | 2026-02-09 |
| D5 | Investimentos | Calculo de P/L absoluto e percentual por ativo e consolidado | Todo | 0% | Alto: depende de D2 + D4 |  | 2026-02-09 |
| D6 | Investimentos | Resiliencia BRAPI (timeout, retry, tratamento de erro, cache curto) | Todo | 0% | Alto: indisponibilidade externa pode quebrar fluxo |  | 2026-02-09 |
| D7 | Investimentos | Endpoint de evolucao historica da carteira por periodo | Todo | 0% | Medio: depende de modelagem de operacoes |  | 2026-02-09 |
| D8 | Investimentos | Expandir carteira para acoes, FII, CDB, CDI etc. + BRAPI + ganho/perda temporal | Todo | 0% | Alto: escopo amplo e multiplas regras de produto |  | 2026-02-09 |
| E1 | Metas | Criar model `Goal` | Todo | 0% | Medio |  | 2026-02-09 |
| E2 | Metas | Criar CRUD de metas (`/goals`) | Todo | 0% | Medio |  | 2026-02-09 |
| E3 | Metas | Servico de planejamento (curto/medio/longo prazo) | Todo | 0% | Alto: regra de negocio central |  | 2026-02-09 |
| E4 | Metas | Calcular plano por renda, gastos e capacidade de aporte | Todo | 0% | Alto |  | 2026-02-09 |
| E5 | Metas | Expor recomendacoes acionaveis com data estimada | Todo | 0% | Medio |  | 2026-02-09 |
| E6 | Metas | Endpoint de simulacao sem persistencia (what-if) | Todo | 0% | Medio |  | 2026-02-09 |
| F1 | Auxiliares | CRUD de `Tag` | Todo | 0% | Baixo |  | 2026-02-09 |
| F2 | Auxiliares | CRUD de `Account` | Todo | 0% | Baixo |  | 2026-02-09 |
| F3 | Auxiliares | CRUD de `CreditCard` | Todo | 0% | Baixo |  | 2026-02-09 |
| F4 | Auxiliares | Integrar `Tag/Account/CreditCard` com transacoes e validacoes | Todo | 0% | Medio |  | 2026-02-09 |
| G1 | Qualidade | Completar suite de testes por dominio | In Progress | 75% | Medio: lacunas em cenarios complexos | 497f901, f3ef3c0 | 2026-02-09 |
| G2 | Qualidade | Testes de integracao BRAPI com mocks/fakes | Todo | 20% | Medio: confiabilidade do provider externo | 497f901 | 2026-02-09 |
| G3 | Qualidade | Enforce de cobertura minima no CI | In Progress | 80% | Baixo | 497f901, 7f0ac66 | 2026-02-09 |
| G4 | Qualidade | Pipeline CI para lint, type-check, testes e gates de qualidade | In Progress | 85% | Baixo | 842a656, 7f0ac66 | 2026-02-09 |
| G5 | Qualidade | Seed de dados para ambiente local | Todo | 0% | Baixo |  | 2026-02-09 |
| H1 | Arquitetura | Adicionar suporte a GraphQL | Todo | 0% | Alto: impacto transversal na API |  | 2026-02-09 |
| H2 | Seguranca | Implementar rate limit por rota/usuario/IP | Todo | 0% | Alto: requisito de protecao operacional |  | 2026-02-09 |
| H3 | Seguranca | Hardening de validacao/sanitizacao/authz/headers/auditoria | Todo | 0% | Alto: controle de risco de seguranca |  | 2026-02-09 |
| X1 | Tech Debt | Remover/atualizar TODO desatualizado sobre enums em transacoes | Todo | 0% | Baixo: clareza de manutencao |  | 2026-02-09 |

## Registro de progresso recente

| Data | Item | Atualizacao | Commit |
|---|---|---|---|
| 2026-02-09 | C2 | Job de recorrencia + servico idempotente para gerar ocorrencias | f3ef3c0 |
| 2026-02-09 | C5 | Endpoint `GET /transactions/expenses` com filtros de periodo, paginacao, ordenacao e metricas | f3ef3c0 |
| 2026-02-09 | C4 | Endpoint `GET /transactions/dashboard` com totais, contagens e top categorias no contrato legado/v2 | pending-commit |
| 2026-02-09 | C4/G1 | Refatoracao com `TransactionAnalyticsService` + suite validada sem regressao | pending-commit |
| 2026-02-09 | G4 | Correcao de lint local (`flake8`/`pyflakes`) com pin de compatibilidade no ambiente dev | pending-commit |
| 2026-02-09 | G4 | Pipeline CI com gate de qualidade/Sonar e validacoes locais | 7f0ac66 |
| 2026-02-09 | H1 (fase 1) | Base GraphQL criada com endpoint `/graphql` + queries/mutations iniciais por controller | pending-commit |
| 2026-02-09 | D (observacao) | Restaurados arquivos deletados acidentalmente: ticker/carteira | n/a |

## Proxima prioridade sugerida
- D1: iniciar modelagem de operacoes de investimento.
- A2: alinhar Swagger 100% com contrato atual.

## Plano GraphQL por Controller

| ID | Controller | Escopo GraphQL | Status | Progresso | Risco | Commit |
|---|---|---|---|---:|---|---|
| H1-AUTH | `auth_controller` | `registerUser`, `login`, `logout` | In Progress | 70% | Medio: manter mesma politica de token do REST | pending-commit |
| H1-USER | `user_controller` | `me`, `updateUserProfile` | In Progress | 60% | Medio: consistencia das validacoes de perfil | pending-commit |
| H1-TRANSACTIONS | `transaction_controller` | `transactions`, `transactionSummary`, `transactionDashboard`, `createTransaction`, `deleteTransaction` | In Progress | 55% | Alto: nao divergir das regras de recorrencia/parcelamento | pending-commit |
| H1-WALLET | `wallet_controller` | `walletEntries`, `walletHistory`, `addWalletEntry`, `updateWalletEntry`, `deleteWalletEntry` | In Progress | 50% | Alto: consistencia de calculo e historico | pending-commit |
| H1-TICKER | `ticker_controller` | `tickers`, `addTicker`, `deleteTicker` | In Progress | 70% | Baixo | pending-commit |
| H1-HARDENING | `graphql_controller` | autorização fina por operação, limites de complexidade/profundidade, observabilidade | Todo | 10% | Alto: segurança/performance |  |
