# Rate Limit Redis Runbook

## Objetivo
Operar o rate-limit distribuído com Redis em ambientes multi-instância, com comportamento fail-closed em produção.

## Variáveis de ambiente
- `RATE_LIMIT_ENABLED=true`
- `RATE_LIMIT_BACKEND=redis`
- `RATE_LIMIT_REDIS_URL=redis://<host>:6379/0`
- `RATE_LIMIT_FAIL_CLOSED=true`
- `RATE_LIMIT_TRUST_PROXY_HEADERS=true` (quando atrás de Nginx/ALB)

## Comportamento esperado
- Se Redis estiver saudável:
  - backend ativo = `redis`
  - contadores globais compartilhados entre réplicas.
- Se Redis estiver indisponível e `RATE_LIMIT_FAIL_CLOSED=true`:
  - API retorna `503` com código `RATE_LIMIT_BACKEND_UNAVAILABLE`.
- Se Redis estiver indisponível e `RATE_LIMIT_FAIL_CLOSED=false`:
  - fallback para memória local.

## Observabilidade
Logs:
- `rate_limit_backend_config ...`
- `rate_limit_fail_closed_active ...`
- `rate_limit_backend_unavailable ...`
- `rate_limit_backend_error ...`

Métricas internas (`app.extensions.integration_metrics`):
- `rate_limit.allowed`
- `rate_limit.allowed.<rule>`
- `rate_limit.blocked`
- `rate_limit.blocked.<rule>`
- `rate_limit.backend_unavailable`
- `rate_limit.backend_error`

## Checklist de validação
1. Subir API com `RATE_LIMIT_BACKEND=redis`.
2. Validar log `rate_limit_backend_config ... backend_name=redis ... ready=True`.
3. Fazer burst de requests e validar resposta `429`.
4. Derrubar Redis e validar:
   - `503` em modo fail-closed
   - log `rate_limit_backend_unavailable`.
