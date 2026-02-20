# Product Overview - Auraxis

Ultima atualizacao: 2026-02-20

## Objetivo deste documento
Este documento descreve o produto para P.O., stakeholders e alinhamento de negocio.
Status de execucao, progresso e rastreabilidade de entrega ficam exclusivamente em `TASKS.md`.

## Visao do produto
Auraxis e uma plataforma de gestao financeira pessoal com foco em planejamento e projecoes de investimento.
A proposta central e transformar dados financeiros do usuario em visibilidade de presente e clareza de futuro.

## Problema que resolvemos
1. Usuarios registram movimentacoes, mas nao conseguem transformar isso em direcao financeira pratica.
2. Metas financeiras existem no plano mental, mas faltam simulacoes objetivas de aporte x tempo.
3. Sem um perfil financeiro consistente, recomendacoes tendem a ser genricas e pouco acionaveis.

## Proposta de valor
1. Consolidar estado financeiro atual em uma base confiavel.
2. Permitir simulacoes de metas com cenarios de aporte e prazo.
3. Evoluir para recomendacoes orientativas personalizadas, com explicabilidade.

## Escopo funcional atual (visao consolidada)
1. Autenticacao e sessao com foco em seguranca de acesso.
2. Gestao de transacoes com filtros, dashboard e consultas por periodo.
3. Gestao de carteira e operacoes de investimento com calculos de desempenho.
4. Modulo de metas com CRUD e simulacao de planejamento em REST e GraphQL.
5. Arquitetura de dominio centralizada para reduzir duplicacao entre adapters REST/GraphQL.

## Principios de produto
1. Clareza: regras financeiras e simulacoes precisam ser compreensiveis para o usuario final.
2. Confianca: seguranca e consistencia de dados sao requisitos de base.
3. Evolucao incremental: cada etapa deve adicionar valor sem degradar confiabilidade.
4. Rastreabilidade: decisoes de produto devem ser convertidas em backlog tecnico no `TASKS.md`.

## Direcao de Perfil de Usuario (V1)

### Decisoes aprovadas em 2026-02-20
1. Renda mensal de referencia sera liquida (`monthly_income_net`).
2. Objetivos financeiros no perfil serao campo livre nesta fase.
3. `state_uf` sera opcional no onboarding e editavel posteriormente no perfil.
4. Perfil de investidor sera inicialmente auto declarado pelo usuario.
5. Um questionario curto sera oferecido para apoiar essa autodeclaracao, de forma indicativa (nao diagnostica).

### Taxonomia inicial de perfil de investidor
1. `conservador`
2. `explorador`
3. `entusiasta`

### Campos minimos de perfil para evolucao de personalizacao
1. `name`
2. `birth_date`
3. `monthly_income_net`
4. `state_uf`
5. `occupation`
6. `investor_profile` (auto declarado)
7. `financial_objectives` (texto livre)

### Questionario auxiliar de perfil (diretriz)
1. Deve ser curto e de baixo atrito.
2. Deve gerar uma sugestao de perfil para o usuario validar, sem substituir a autodeclaracao.
3. Deve ser tratado como apoio de produto, nao como recomendacao financeira certificada.

## Direcao futura de IA
1. Identificar padroes de gasto e oportunidades de economia.
2. Traduzir impacto de comportamento financeiro na viabilidade das metas.
3. Entregar orientacoes acionaveis com justificativas claras.

## Guardrails para recursos de IA
1. Consentimento explicito do usuario para analise automatizada.
2. Explicabilidade minima da recomendacao.
3. Privacidade, minimizacao de dados e trilha de auditoria.
4. Modo advisory-only, sem execucao automatica financeira.

## Governanca documental
1. `product.md`: estrategia, direcao e decisoes de produto.
2. `TASKS.md`: backlog executavel, prioridades, riscos, progresso e commits.
