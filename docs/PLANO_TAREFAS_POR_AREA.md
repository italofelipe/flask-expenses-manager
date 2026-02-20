# Plano de Tarefas por Area - Auraxis

Ultima atualizacao: 2026-02-20

## Papel deste documento
Este arquivo organiza o backlog por area de dominio para leitura rapida.

Fonte oficial de status/progresso/risco/commit:
1. `TASKS.md` (source of truth operacional)

Fonte oficial de estrategia e decisao de produto:
1. `product.md`

## Mapa de areas

### Area A - Base de API e contratos
Foco:
1. Padronizacao de contrato de resposta.
2. Coerencia de OpenAPI e schema GraphQL.
3. Nomenclatura e validacao arquitetural.

### Area B - Usuario e perfil financeiro
Foco:
1. Evolucao de perfil para personalizacao.
2. Perfil de investidor auto declarado.
3. Questionario auxiliar para sugestao de perfil.
4. Auditoria e coerencia de dados de perfil.

### Area C - Transacoes
Foco:
1. Operacoes financeiras com filtros e visoes de analise.
2. Resumo mensal, dashboard e consultas por periodo.
3. Endpoints de apoio para decisao financeira.

### Area D - Carteira e investimentos
Foco:
1. Posicoes e operacoes de investimento.
2. Valuation, historico e calculos de desempenho.
3. Resiliencia de integracao com provider externo.

### Area E - Metas e planejamento
Foco:
1. CRUD de metas.
2. Planejamento de curto/medio/longo prazo.
3. Simulacao what-if e recomendacoes acionaveis.

### Area F - Cadastros auxiliares
Foco:
1. `Tag`, `Account`, `CreditCard`.
2. Integracao com filtros e validacoes em transacoes.

### Area G - Qualidade e testes
Foco:
1. Cobertura automatizada por dominio.
2. Gates de qualidade no CI.
3. Seeds e suporte de desenvolvimento local.

### Area H - Seguranca e governanca
Foco:
1. Hardening continuo de API e infraestrutura.
2. Auditoria, observabilidade e resposta a incidentes.
3. Evolucao de politicas e controles de risco.

## Ordem de leitura sugerida
1. `product.md` para contexto de produto.
2. `TASKS.md` para execucao e prioridade.
3. `docs/PROFILE_V1_SPEC.md` para evolucao tecnica do perfil.
4. `docs/API_DOCUMENTATION.md` para contrato as-is.
