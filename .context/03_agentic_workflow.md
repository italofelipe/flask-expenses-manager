# Agentic AI Workflow

## Objetivo
Permitir que agentes diferentes (ou sessoes diferentes) consigam continuar o trabalho com baixa perda de contexto.

## Loop operacional de agente
1. Bootstrap
- Ler `.context/README.md` e `01_sources_of_truth.md`.
- Ler `TASKS.md` para identificar estado atual.
- Ler docs tecnicas diretamente relacionadas ao bloco atual.

2. Planejamento curto
- Definir bloco de execucao e ordem de commits.
- Separar tarefas executaveis pelo agente vs tarefas dependentes de humano.

3. Execucao incremental
- Implementar por fatias pequenas.
- Validar continuamente (lint/testes/gates).
- Atualizar docs de rastreabilidade ao fim de cada fatia.

4. Handoff
- Registrar em `.context/handoffs/` usando `templates/handoff_template.md` quando o bloco nao terminar na mesma sessao.

## Regras de ouro para agentes
- Nao operar em ambiguidades de produto sem registrar suposicao.
- Nao ocultar riscos conhecidos; registrar no backlog tecnico.
- Nao abrir escopo sem explicitar impacto.
- Preferir alteracoes deterministicas e reversiveis.

## Contrato de handoff entre agentes
Cada handoff deve conter:
- Estado atual (o que foi entregue).
- Pendencias imediatas (next actions).
- Riscos/bloqueios.
- Comandos de validacao usados.
- Commits relacionados.
