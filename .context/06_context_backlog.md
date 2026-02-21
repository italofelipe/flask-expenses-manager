# Context Backlog (evolucao da base de conhecimento)

## Ja implementado

- Estrutura inicial `.context` com bootstrap operacional.
- Workflow SDD documentado.
- Workflow agentico e template de handoff definidos.
- CLAUDE.md com diretiva operacional e integracao com .context/.
- Security hardening das tools do ai_squad/ (tool_security.py).
- Integracao do ai_squad/ com a base de conhecimento .context/.
- Ciclo operacional multi-agente documentado (07_operational_cycle.md).
- Template de feature card para TASKS.md (feature_card_template.md).
- Template de delivery report pos-entrega (delivery_report_template.md).
- Diretorio reports/ para armazenar delivery reports.
- CLAUDE.md atualizado com ciclo de entrega e colaboracao multi-agente (Claude, Gemini, Gepeto).

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
