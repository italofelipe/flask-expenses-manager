# ADR-0001: Validation Strategy

- Status: Accepted
- Date: 2026-02-20
- Deciders: Engineering
- Related backlog: `A4` (`TASKS.md`)

## Context
O projeto hoje usa Marshmallow + Webargs de ponta a ponta em REST e em partes críticas de GraphQL.
Também existe discussão sobre introdução gradual de Pydantic, mas sem plano formal e com risco de duplicar schemas/regra de negócio.

## Decision
Adotar **Marshmallow + Webargs como estratégia única de validação em runtime** até novo ADR explícito.

Regras derivadas:
1. Novos endpoints REST devem usar schemas Marshmallow.
2. Regras de validação compartilhadas devem viver em schema/serviço reutilizável, sem duplicar validação por controller.
3. Pydantic não deve ser introduzido no runtime da API sem ADR de revisão.
4. Se Pydantic for necessário no futuro, a adoção deve ocorrer por domínio com migração controlada e sem coexistência indefinida.

## Consequences
### Positivas
- Reduz complexidade cognitiva e custo de manutenção.
- Evita drift de contrato por dupla implementação de schema.
- Mantém alinhamento com stack atual já coberta por testes e CI.

### Negativas
- Perde-se no curto prazo recursos específicos de tipagem/runtime do ecossistema Pydantic.
- Migração futura exigirá ADR de revisão e plano de transição.

## Guardrails
- Proibido criar novos validadores runtime fora do padrão Marshmallow/Webargs sem exceção documentada.
- Toda mudança de validação deve ter testes de contrato (payload válido e inválido).
