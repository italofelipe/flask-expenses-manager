# Sources of Truth

## Hierarquia de autoridade
1. `TASKS.md` - backlog, status, progresso, riscos e rastreabilidade.
2. `product.md` - visao de produto, escopo funcional e direcao de negocio.
3. `steering.md` - governanca de execucao de IA/engenharia.
4. `docs/` - runbooks, ADRs, seguranca, CI/CD, arquitetura complementar.

## Regra anti-conflito
Quando houver divergencia entre documentos:
1. `TASKS.md` governa status/prioridade.
2. `product.md` governa intencao de produto.
3. `steering.md` governa como executar.
4. `docs/adr/*.md` governa decisoes arquiteturais registradas.

## Onde atualizar cada tipo de mudanca
- Mudou status de tarefa: atualizar `TASKS.md`.
- Mudou direcao de produto: atualizar `product.md`.
- Mudou forma de trabalho/regras de engenharia: atualizar `steering.md`.
- Mudou design tecnico significativo: atualizar ADR em `docs/adr/`.
- Mudou operacao/deploy/seguranca: atualizar runbook correspondente em `docs/`.

## Checklist minimo de sincronizacao documental
- [ ] `TASKS.md` refletindo o que foi entregue.
- [ ] Documentos tecnicos impactados atualizados.
- [ ] Riscos e debitos tecnicos explicitos (quando existirem).
- [ ] Commit(s) rastreaveis para cada bloco de alteracao.
