# Sources of Truth

## Hierarquia de autoridade

1. **GitHub Projects** (https://github.com/users/italofelipe/projects/1) — backlog, status, prioridade e rastreabilidade de tasks. Source of truth canônico desde 2026-04-13.
2. `product.md` — visão de produto, escopo funcional e direção de negócio.
3. `steering.md` — governança de execução de IA/engenharia.
4. `docs/` — runbooks, ADRs, segurança, CI/CD, arquitetura complementar.

> **TASKS.md — DEPRECATED** (2026-04-13): descontinuado em favor do GitHub Projects. Não atualizar.

## Regra anti-conflito

Quando houver divergência entre documentos:
1. **GitHub Projects** governa status/prioridade.
2. `product.md` governa intenção de produto.
3. `steering.md` governa como executar.
4. `docs/adr/*.md` governa decisões arquiteturais registradas.

## Onde atualizar cada tipo de mudança

- Mudou status de tarefa → **GitHub Projects** (issue + project item).
- Mudou direção de produto → `product.md`.
- Mudou forma de trabalho/regras de engenharia → `steering.md`.
- Mudou design técnico significativo → ADR em `docs/adr/`.
- Mudou operação/deploy/segurança → runbook correspondente em `docs/`.

## Checklist mínimo de sincronização documental

- [ ] Issue no GitHub com critérios de aceite e commit hash referenciado.
- [ ] Documentos técnicos impactados atualizados.
- [ ] Riscos e débitos técnicos explícitos (quando existirem).
- [ ] Commit(s) rastreáveis para cada bloco de alteração.
