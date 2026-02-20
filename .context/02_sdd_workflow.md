# SDD Workflow (Spec-Driven Development)

## Objetivo
Garantir que implementacoes sejam dirigidas por especificacao explicita antes de codigo.

## Fluxo padrao
1. Discovery
- Definir problema, objetivo, restricoes e criterios de aceite.
- Confirmar impactos em REST, GraphQL, dominio e dados.

2. Spec
- Criar/atualizar especificacao usando `templates/feature_spec_template.md`.
- Incluir contrato de entrada/saida, erros esperados, invariantes e limites.

3. Design
- Definir componentes afetados.
- Registrar trade-offs e, se necessario, ADR.

4. Planejamento
- Quebrar entrega em tarefas pequenas e rollback-safe.
- Atualizar `TASKS.md` com status inicial e riscos.

5. Execucao
- Criar branch convencional.
- Implementar em commits pequenos por responsabilidade.

6. Verificacao
- Rodar gates locais.
- Validar comportamento em testes de regressao.

7. Registro
- Atualizar `TASKS.md` e docs impactadas.
- Registrar debito tecnico residual quando aplicavel.

## Definicao de pronto para SDD
- Especificacao e codigo convergentes.
- Testes cobrindo regra principal e bordas criticas.
- Sem regressao de contrato REST/GraphQL.
- Rastreabilidade de commit por tarefa/bloco.
