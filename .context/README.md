# .context - Base de Conhecimento para IA

## Objetivo
Esta pasta e a camada de contexto operacional para agentes de IA neste repositorio.
Ela nao substitui os documentos oficiais; ela organiza o que ler, em que ordem, e como executar com previsibilidade.

## Ordem de leitura recomendada (bootstrap de sessao)
1. `.context/01_sources_of_truth.md`
2. `.context/04_architecture_snapshot.md`
3. `.context/02_sdd_workflow.md`
4. `.context/03_agentic_workflow.md`
5. `.context/05_quality_and_gates.md`
6. `TASKS.md` (status e backlog)

## Invariantes do projeto
- Backlog, status e progresso: `TASKS.md`.
- Direcao de produto e escopo funcional: `product.md`.
- Modo de execucao de engenharia/IA: `steering.md`.
- `README.md` do repo fica curto; detalhes ficam em docs dedicadas.

## Convencoes obrigatorias
- Conventional branching (`feat/...`, `fix/...`, `refactor/...`, `docs/...`, etc).
- Conventional commits.
- Nunca commitar diretamente na `master`.
- Commits pequenos e granulares (rollback seguro).

## Conteudo desta pasta
- `01_sources_of_truth.md`: mapa de autoridade documental.
- `02_sdd_workflow.md`: fluxo Spec-Driven Development adotado.
- `03_agentic_workflow.md`: protocolo de operacao para agentes.
- `04_architecture_snapshot.md`: snapshot arquitetural para orientacao rapida.
- `05_quality_and_gates.md`: gates locais/CI/CD e criterios de pronto.
- `06_context_backlog.md`: melhorias necessarias na propria base de contexto.
- `templates/feature_spec_template.md`: template de especificacao.
- `templates/handoff_template.md`: template de handoff entre agentes/sessoes.
