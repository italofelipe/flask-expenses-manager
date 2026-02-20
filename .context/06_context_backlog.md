# Context Backlog (evolucao da base de conhecimento)

## Ja implementado

- Estrutura inicial `.context` com bootstrap operacional.
- Workflow SDD documentado.
- Workflow agentico e template de handoff definidos.
- CLAUDE.md com diretiva operacional e integracao com .context/.
- Security hardening das tools do ai_squad/ (tool_security.py).
- Integracao do ai_squad/ com a base de conhecimento .context/.

## Proximos incrementos recomendados

1. Adicionar check de CI para garantir que specs/handoffs sejam atualizados quando arquivos criticos mudarem.
2. Criar ownership documental (quem aprova mudancas em `product.md`, `steering.md`, `TASKS.md`).
3. Criar taxonomia padrao de severidade de risco e debito tecnico.
4. Definir periodicidade de revisao da base `.context` (semanal/por release).
5. Versionar templates de specs por tipo de entrega (feature, refactor, incidente).
6. Validar que CLAUDE.md permanece sincronizado com steering.md e .context/05 em cada release.
7. Adicionar protocolo de rollback/abort ao agentic workflow (o que fazer quando um gate falha no meio da execucao).

## Nota

A pasta `.context` sozinha ajuda bastante, mas nao fecha o ciclo sem:

- disciplina de atualizacao,
- templates obrigatorios,
- e gate de processo no CI.
