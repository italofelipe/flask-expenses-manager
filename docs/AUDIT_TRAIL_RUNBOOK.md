# Audit Trail Runbook

## Objetivo
Operar trilha de auditoria persistente com retenção e busca por `request_id`.

## Variáveis de ambiente
- `AUDIT_TRAIL_ENABLED=true`
- `AUDIT_PERSISTENCE_ENABLED=true`
- `AUDIT_PATH_PREFIXES=/auth/,/user/,/transactions/,/wallet,/graphql`
- `AUDIT_RETENTION_ENABLED=true`
- `AUDIT_RETENTION_DAYS=90`
- `AUDIT_RETENTION_SWEEP_INTERVAL_SECONDS=3600`

## Persistência
- Tabela: `audit_events`
- Índices:
  - `ix_audit_events_request_id`
  - `ix_audit_events_created_at`

## Busca por request_id
Comando:
```bash
python scripts/manage_audit_events.py search --request-id <REQUEST_ID> --limit 50
```

Saída:
- JSON com `count` e `items` ordenados por `created_at desc`.

## Retenção
Purge manual:
```bash
python scripts/manage_audit_events.py purge --retention-days 90
```

Purge automática em runtime:
- Executada no fluxo de auditoria com intervalo configurável por `AUDIT_RETENTION_SWEEP_INTERVAL_SECONDS`.
- Log de remoção:
  - `audit_retention_prune_deleted count=<N> retention_days=<D>`
