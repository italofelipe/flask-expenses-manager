# PostgreSQL Tuning — Auraxis API

**Last updated:** 2026-04-12
**Issue:** PERF-3 (#971)

---

## Slow Query Log

Enabled in production on 2026-04-12.

```sql
ALTER SYSTEM SET log_min_duration_statement = 500;
SELECT pg_reload_conf();
```

| Setting | Value | Notes |
|:--------|:------|:------|
| `log_min_duration_statement` | `500` (ms) | Logs any query taking >500ms |
| Previous value | `-1` (disabled) | No slow query logging before 2026-04-12 |

### Viewing slow queries

```bash
# Via SSM
aws ssm start-session --target i-0057e3b52162f78f8

# Check PG logs inside container
docker logs auraxis-db-1 --since 1h 2>&1 | grep "duration:"

# Or query the setting
docker exec auraxis-db-1 psql -U flaskuser -d flaskdb -c "SHOW log_min_duration_statement;"
```

### Tuning the threshold

If too noisy, increase to 1000ms. If investigating a specific issue, temporarily lower to 100ms:

```sql
-- Temporary (resets on restart)
SET log_min_duration_statement = 100;

-- Persistent
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();
```

## Performance Indexes

Applied during the 2026-04-12 index audit. See alembic migrations for the full list.

Key indexes:
- `ix_transactions_user_deleted` — (user_id, deleted) on transactions
- `ix_transactions_user_deleted_due_date` — (user_id, deleted, due_date) on transactions
- `ix_transactions_user_created` — (user_id, created_at DESC) on transactions
- `ix_goals_user_status` — (user_id, status) on goals
- `ix_goals_user_priority_created_at` — (user_id, priority, created_at) on goals
- `ix_wallets_user_id` — (user_id) on wallets
- `ix_wallets_user_should_be_on_wallet` — (user_id, should_be_on_wallet) on wallets
- `ix_tags_user_id` — (user_id) on tags
- `ix_accounts_user_id` — (user_id) on accounts

### Verifying indexes in prod

```bash
docker exec auraxis-db-1 psql -U flaskuser -d flaskdb -c "\di+ ix_*"
```
