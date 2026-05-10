## Descrição

<!-- Explique o que foi implementado e por quê. -->

Closes #<!-- número da issue -->

## Tipo de mudança

- [ ] Feature nova (endpoint REST ou mutation GraphQL)
- [ ] Bug fix
- [ ] Refactor
- [ ] Migration de banco de dados
- [ ] Documentação / infraestrutura

## Checklist de qualidade

- [ ] `bash scripts/run_ci_quality_local.sh --local` passou
- [ ] Coverage **não** regrediu abaixo de 85%
- [ ] Testes unitários e de integração criados/atualizados

## Checklist de migrations (se houver)

- [ ] **Sem migration** — OU —
- [ ] `bash scripts/test_migrations_local.sh` passou (up + down)
- [ ] Migration usa `native_enum=False` para enums (não `native_enum=True`)
- [ ] Sem `op.get_bind()` — usar `op.get_context().connection`

## Checklist de contratos (se houver endpoint novo/modificado)

- [ ] **Sem mudança de contrato** — OU —
- [ ] Endpoint documentado no OpenAPI (`openapi.json` atualizado)
- [ ] Snapshot propagado para consumers (auraxis-web, auraxis-app)
- [ ] ENRICHMENT adicionado em `scripts/openapi_to_postman.py` se endpoint tem validação customizada

## Checklist de segurança

- [ ] Nenhum secret, token ou credencial commitada
- [ ] Endpoint novo protegido com `@require_auth` (se aplicável)
- [ ] Sem `print()` com dados sensíveis nos logs
