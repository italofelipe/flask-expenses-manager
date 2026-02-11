# Plano de Tarefas por Área - Not Enough Cash, Stranger!

> Fonte de verdade para acompanhamento operacional (status, progresso, risco e commit): `TASKS.md`.

## 1) Diagnóstico rápido (estado atual)

### 1.1 Autenticação e usuário
- Implementado:
  - Registro, login e logout com JWT (`/auth/register`, `/auth/login`, `/auth/logout`).
  - Controle de token revogado via `current_jti` no usuário.
  - Atualização de perfil (`/user/profile`) com campos financeiros e validações básicas.
  - Endpoint consolidado `/user/me` com dados do usuário + transações + carteira.
- Pendências:
  - Não há refresh token.
  - Falta padronização de respostas de erro/sucesso entre controllers.

### 1.2 Transações (receitas e despesas)
- Implementado:
  - CRUD principal de transações (`/transactions`).
  - Soft delete, restore e force delete.
  - Campos para recorrência e parcelamento; criação de parcelas automáticas.
  - Resumo mensal (`/transactions/summary?month=YYYY-MM`).
- Pendências:
  - Regras de negócio de recorrência/parcelamento podem ser reforçadas (consistência entre datas, contagem, etc.).

### 1.3 Investimentos / carteira
- Implementado:
  - CRUD de carteira (`/wallet`) com suporte a ativo com `ticker` ou valor fixo.
  - Integração BRAPI para cotação atual (`InvestmentService.get_market_price`).
  - Cálculo de `estimated_value_on_create_date` e histórico de alterações na carteira.
- Pendências:
  - Não existe uma entidade/endpoint completo de operações por ativo (compra/venda por data), só snapshot em carteira.
  - Falta cálculo formal de:
    - quanto investiu no dia (baseado em data de operação),
    - valor atual consolidado da carteira,
    - P/L (lucro/prejuízo) por ativo e total.
  - Dependência de BRAPI sem cache/retry/timeout explícito e sem fallback estruturado.

### 1.4 Metas financeiras
- Implementado:
  - Campos no perfil (`monthly_expenses`, `initial_investment`, `monthly_investment`, `investment_goal_date`).
- Pendências:
  - Não existe domínio de metas (model, schema, endpoints, serviço de cálculo, simulações).
  - Não há geração de planos curto/médio/longo prazo.

### 1.5 Cadastros auxiliares (conta, cartão, tag)
- Implementado:
  - Models e schemas de `Account`, `CreditCard`, `Tag`.
- Pendências:
  - Não há controllers/rotas para CRUD desses recursos.

### 1.6 Qualidade técnica
- Implementado:
  - Configuração de `black`, `isort`, `flake8`, `mypy` em pre-commit.
  - Documentação Swagger via apispec.
- Pendências:
  - Projeto usa Marshmallow/Webargs; não há Pydantic no código atual.
  - Cobertura geral já está acima de 85%, mas faltam testes de alguns fluxos críticos de domínio.
  - Documentação externa está parcialmente desatualizada em relação às rotas reais (ex.: `/ticker` vs `/wallet`, caminhos antigos de auth).

---

## 2) Backlog por área (tarefas objetivas)

## Área A - Base e consistência da API
- [ ] A1. Padronizar contrato de resposta (sucesso/erro) em todos os endpoints.
- Status A1 (parcial concluído):
  - [x] `auth` com retrocompatibilidade (`legacy` + `X-API-Contract: v2`)
  - [x] `user` com retrocompatibilidade (`legacy` + `X-API-Contract: v2`)
  - [x] `transactions` com retrocompatibilidade (`legacy` + `X-API-Contract: v2`)
  - [x] `wallet` com retrocompatibilidade (`legacy` + `X-API-Contract: v2`)
  - [ ] Domínios futuros (`goals`, cadastros auxiliares) ainda não implementados
- [ ] A2. Revisar documentação OpenAPI para refletir rotas reais (`/auth/*`, `/transactions/*`, `/wallet/*`).
- [ ] A3. Remover inconsistências de nomenclatura (ticker/wallet/investment) no código e docs.
- [ ] A4. Definir estratégia única de validação: manter Marshmallow ou introduzir Pydantic de forma gradual.

## Área B - Usuário e perfil financeiro
- [ ] B1. Criar endpoint de leitura exclusiva de perfil (separado de `/user/me` para payload menor).
- [ ] B2. Melhorar validações de perfil (regras de coerência entre renda, gastos, investimento mensal/meta).
- [ ] B3. Adicionar auditoria de atualização de perfil (quem alterou, quando, mudanças relevantes).

## Área C - Transações (receitas/despesas)
- [x] C1. Corrigir listagem de transações ativas com filtros e paginação reais no banco.
- [x] C2. Validar regras fortes de recorrência:
  - [x] `start_date <= end_date`
  - [x] criação automática de ocorrências futuras (serviço idempotente + job agendado)
  - [x] prevenção de duplicidade
- [x] C3. Consolidar regras de parcelamento (soma das parcelas = total, arredondamento final).
- [x] C4. Criar endpoint de dashboard mensal (receitas, despesas, saldo, categorias principais).
- [x] C5. Criar endpoint de despesas por período com paginação, ordenação e métricas agregadas.

## Área D - Investimentos
- [ ] D1. Criar entidade de operações de investimento (`buy`/`sell`) com data, preço, quantidade, taxas.
- [ ] D2. Implementar cálculo de custo médio por ativo e posição atual.
- [ ] D3. Implementar cálculo "quanto investiu no dia" por data de operação.
- [ ] D4. Implementar cálculo "quanto vale hoje" por ativo e consolidado (BRAPI + fallback).
- [ ] D5. Implementar P/L absoluto e percentual por ativo e total.
- [ ] D6. Adicionar resiliência BRAPI (timeout, retry, tratamento de erro e cache curto).
- [ ] D7. Criar endpoint de evolução histórica da carteira por período.
- [ ] D8. Expandir feature de Carteira para múltiplos produtos (`ações`, `FII`, `CDB`, `CDI` e similares), com:
  - integração BRAPI para preço na data do aporte e preço atual,
  - cálculo de ganho/perda no tempo por posição e consolidado,
  - modelagem modular e testável para suportar novos tipos de investimento.

## Área E - Metas financeiras
- [ ] E1. Criar model `Goal` (nome, valor alvo, prazo, prioridade, status).
- [ ] E2. Criar CRUD de metas (`/goals`).
- [ ] E3. Criar serviço de planejamento com 3 cenários:
  - curto prazo (3-6 meses)
  - médio prazo (1-2 anos)
  - longo prazo (3+ anos)
- [ ] E4. Calcular plano com base em renda, gastos mensais e capacidade de aporte.
- [ ] E5. Expor recomendações acionáveis (aporte mensal sugerido, corte de gastos necessário, data estimada de atingimento).
- [ ] E6. Criar endpoint de simulação de meta sem persistência (what-if).

## Área F - Cadastros auxiliares
- [ ] F1. Implementar CRUD de `Tag`.
- [ ] F2. Implementar CRUD de `Account`.
- [ ] F3. Implementar CRUD de `CreditCard`.
- [ ] F4. Integrar esses recursos com filtros e validações nas transações.

## Área G - Testes, qualidade e operação
- [ ] G1. Montar suíte de testes por domínio (auth, user, transactions, wallet, goals).
- [ ] G2. Adicionar testes de integração para BRAPI com mocks/fakes.
- [ ] G3. Definir cobertura mínima (ex.: 80%) no CI.
- [ ] G4. Criar pipeline CI para lint, type-check e testes.
- [ ] G5. Criar dados seed para ambiente local (usuário demo, transações, carteira, metas).

## Área H - Arquitetura e segurança (futuro)
- [ ] H1. Adicionar suporte a GraphQL em toda a aplicação (schema unificado, resolvers por domínio, autenticação e autorização).
- [ ] H2. Implementar rate limiting por rota/usuário/IP (incluindo proteção para auth e endpoints sensíveis).
- [ ] H3. Reforçar segurança de entrada/saída:
  - validação e sanitização de payload
  - hardening de autenticação/autorização
  - revisão de headers de segurança e políticas de erro
  - trilha de auditoria para eventos sensíveis.

---

## 3) Plano de execução sugerido (ordem prática)

## Fase 0 - Alinhamento e estabilização (rápida)
- A2, A3, A1.
- Objetivo: documentação e contratos coerentes antes de crescer features.

## Fase 1 - Núcleo financeiro confiável
- C1, C3, F1, F2, F3, F4.
- Objetivo: fechar base de receitas/despesas com categorias/contas/cartões funcionando ponta a ponta.

## Fase 2 - Investimentos de verdade
- D1, D2, D3, D4, D5, D6.
- Objetivo: sair de snapshot de carteira para controle por operação e valuation confiável.

## Fase 3 - Metas e planejamento
- E1, E2, E3, E4, E5, E6.
- Objetivo: transformar dados financeiros em planos de curto/médio/longo prazo.

## Fase 4 - Recorrência inteligente e fechamento
- C2, D7, B2, B3.
- Objetivo: automações, histórico evolutivo e robustez final.

## Fase 5 - Qualidade e entrega contínua (transversal, mas fechar aqui)
- G1, G2, G3, G4, G5.
- Objetivo: garantir evolução segura e sustentável.

## Fase 6 - Segurança e evolução de API
- H1, H2, H3.
- Objetivo: ampliar capacidades de integração (GraphQL) com baseline de segurança reforçado.

---

## 4) Critérios de pronto (Definition of Done)
- [ ] Endpoint documentado no Swagger + exemplo de request/response.
- [ ] Validações de entrada e regras de negócio cobertas por testes.
- [ ] Testes automatizados passando no CI.
- [ ] Erros retornando payload padronizado.
- [ ] Sem quebra de compatibilidade não planejada.

---

## 5) Observações importantes encontradas
- O projeto atual não usa Pydantic no runtime (usa Marshmallow/Webargs).
- Existem referências na documentação para rotas/recursos que ainda não estão implementados (especialmente `ticker` separado e alguns caminhos antigos de auth/transação).
- O módulo de metas ainda não existe e deve ser tratado como nova feature de domínio.
- A superfície de ticker segue somente via GraphQL e domínio de carteira; o controller REST legado de ticker foi removido para evitar drift operacional.
