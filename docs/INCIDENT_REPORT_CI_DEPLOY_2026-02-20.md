# Incident Report - CI Deploy failures (DEV/PROD)

Data: 2026-02-20

## Escopo
Falhas recorrentes no pipeline de deploy GitHub Actions para DEV/PROD.

## Sintomas observados
1. Deploy interrompido com `container auraxis-web-1 is unhealthy`.
2. Smoke check GraphQL falhando com `expected HTTP 400, got 405`.
3. Migração falhando com:
   - `DuplicateTable: relation "audit_events" already exists`
   - `Can't locate revision identified by 'c3f8d2a1b9e4'`

## Causa raiz (RCA)

### RCA-1: Baseline Alembic vs schema legado
Contexto:
1. Ambiente já tinha tabelas criadas antes da baseline de migrations.
2. `flask db upgrade` tentou criar tabelas já existentes.

Impacto:
1. `web` não sobe.
2. Healthcheck do container falha.

Correção aplicada:
1. Entry point de produção agora detecta schema legado sem `alembic_version`.
2. Executa `flask db stamp 69f75d73808e` antes do `flask db upgrade`.

### RCA-2: Deploy de ref incorreta no workflow
Contexto:
1. Run manual com `git_ref` vazio estava resolvendo para SHA/contexto não esperado.
2. Instância recebeu checkout de commit antigo (sem revision migration esperada).

Impacto:
1. `Can't locate revision identified by 'c3f8d2a1b9e4'`.
2. Script e comportamento de smoke podem não refletir o branch que estava sendo validado.

Correção aplicada:
1. Workflow de deploy passou a resolver refs assim:
   - `push`: `origin/master`
   - `workflow_dispatch` com `git_ref` vazio: `origin/${GITHUB_REF_NAME}`
   - `prod` manual com `git_ref` vazio: `origin/master`
2. Logs e summary agora exibem `event`, `github_ref`, `github_ref_name`, `input_ref`, `resolved_ref`.

### RCA-3: Smoke GraphQL com redirect HTTP->HTTPS
Contexto:
1. Smoke usa base URL `http://...`.
2. Reverse proxy redireciona para `https://...` com 301.
3. Cliente padrão convertia `POST` em `GET` no redirect.

Impacto:
1. `/graphql` respondeu `405` (endpoint aceita POST).

Correção aplicada:
1. `scripts/http_smoke_check.py` passou a seguir redirect manualmente preservando método/body.
2. Teste de regressão criado para esse caso em `tests/scripts/test_http_smoke_check.py`.

## Por que apareceu mais no CI do que local
1. CI usa domínio público com redirect real HTTP->HTTPS.
2. CI opera contra banco persistente em EC2 (estado histórico), diferente de DB efêmero local.
3. Deploy manual sem ref explícita é mais suscetível a ambiguidades de contexto.

## Ações de mitigação recomendadas
1. Definir `AURAXIS_DEV_BASE_URL` como `https://dev.api.auraxis.com.br`.
2. Em `workflow_dispatch`, informar `git_ref` explicitamente para testes de branch (ex.: `origin/fix/...`).
3. Adicionar verificação pós-deploy:
   - `flask db current`
   - leitura de `alembic_version`
4. Evitar reaproveitar schema sem versionamento Alembic em ambientes de longa duração.
5. Manter teste de smoke para redirect com preservação de método.

## Status
1. Diagnóstico de deploy fortalecido.
2. Correções de migration bootstrap e smoke redirect implementadas.
3. Correção de resolução de ref no workflow implementada.
