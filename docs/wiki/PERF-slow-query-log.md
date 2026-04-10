# Slow Query Log — PostgreSQL

## O que é

Qualquer query com duração ≥ 500ms é registrada automaticamente no log do container `db`.
Isso permite identificar N+1s, falta de índices e queries não otimizadas sem instrumentação extra na aplicação.

## Como visualizar

```bash
# Ver queries lentas em tempo real
docker compose logs -f db | grep "duration:"

# Filtrar as últimas 50 ocorrências
docker compose logs db | grep "duration:" | tail -50

# Extrair apenas o SQL e a duração
docker compose logs db | grep "duration:" | sed 's/.*duration: //;s/  execute.*//' | sort -rn | head -20
```

## Configuração aplicada

Definida via `command` no `docker-compose.yml` e `docker-compose.dev.yml`:

| Parâmetro | Valor | Efeito |
|---|---|---|
| `log_min_duration_statement` | `500` | Loga queries com duração ≥ 500ms |
| `log_statement` | `none` | Não loga todas as queries (só as lentas) |
| `log_line_prefix` | `%m [%p] %q%u@%d ` | Timestamp + PID + user@db |

Log rotation: `max-size: 50m`, `max-file: 3` (máximo ~150MB de logs de DB).

## Baseline capturado

Rodar em produção por ≥ 24h antes de aplicar fixes de PERF-GAP-01 (índices) e PERF-GAP-02 (eager loading).

```bash
# Produção: conectar via SSM e visualizar logs do container
aws ssm start-session --target <INSTANCE_ID>
sudo docker logs auraxis-api-db-1 2>&1 | grep "duration:" | tail -100
```

## Produção (EC2 sem Docker Compose db)

O container `db` está comentado no `docker-compose.prod.yml` (aguardando migração para RDS — ver `RDS-Migration-Runbook.md`). O PostgreSQL em produção roda diretamente no EC2.

Para habilitar slow query log temporariamente via psql:

```sql
-- Ativar (sem restart)
ALTER SYSTEM SET log_min_duration_statement = 500;
SELECT pg_reload_conf();

-- Verificar
SHOW log_min_duration_statement;

-- Desativar após coleta
ALTER SYSTEM SET log_min_duration_statement = -1;
SELECT pg_reload_conf();
```

Os logs ficam em `/var/log/postgresql/` ou acessíveis via `sudo journalctl -u postgresql`.

## Próximos passos

Após 24h de coleta:
1. Listar as top-10 queries mais lentas
2. Abrir cards de fix em PERF-GAP-01 (índices) e PERF-GAP-02 (eager loading)
3. Após fixes, confirmar que as queries saíram do log

## Referência

- Issue: [PERF-GAP-03](https://github.com/italofelipe/auraxis-api/issues/941)
- Próximas etapas: PERF-GAP-01 (#939), PERF-GAP-02 (#940)
