# Context Backlog (evolucao da base de conhecimento)

## Ja implementado
- Estrutura inicial `.context` com bootstrap operacional.
- Workflow SDD documentado.
- Workflow agentico e template de handoff definidos.

## Proximos incrementos recomendados
1. Adicionar check de CI para garantir que specs/handoffs sejam atualizados quando arquivos criticos mudarem.
2. Criar ownership documental (quem aprova mudancas em `product.md`, `steering.md`, `TASKS.md`).
3. Criar taxonomia padrao de severidade de risco e debito tecnico.
4. Definir periodicidade de revisao da base `.context` (semanal/por release).
5. Versionar templates de specs por tipo de entrega (feature, refactor, incidente).

## Nota
A pasta `.context` sozinha ajuda bastante, mas nao fecha o ciclo sem:
- disciplina de atualizacao,
- templates obrigatorios,
- e gate de processo no CI.
