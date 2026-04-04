# RDS Migration Runbook — H-INFRA-03

**Issue:** [H-INFRA-03] Separar Postgres para RDS Free Tier + auto-recovery EC2
**GitHub Issue:** #858
**Status:** Phase 1 complete (Terraform config + migration script ready). Phase 2 = human-approved cutover.
**Last updated:** 2026-04-04

---

## Overview

This runbook covers the full cutover from the current Postgres-in-Docker setup
(running on EC2 `i-0057e3b52162f78f8`) to a managed AWS RDS PostgreSQL 16 instance
(`db.t4g.micro`, 20 GB gp3, free tier eligible).

**Why:**
- Docker Postgres on a t2.micro has no automatic backups, no failover, and competes for memory with the app container.
- RDS provides automated daily backups (7-day retention), minor version auto-upgrade, and CloudWatch metrics.
- Separating the data tier from the compute tier enables independent scaling and EC2 auto-recovery without data loss.

---

## Prerequisites

| Requirement | Status | Notes |
|:------------|:------:|:------|
| Terraform RDS config committed | Ready | `infra/api/main.tf` in auraxis-platform |
| Migration script committed | Ready | `scripts/migrate-to-rds.sh` in auraxis-api |
| docker-compose.prod.yml updated | Ready | `db` service commented out with instructions |
| AWS credentials with RDS + EC2 access | Required | via IAM role or profile |
| `postgresql-client` on EC2 | Auto-installed by script | or `apt-get install -y postgresql-client` |
| Maintenance window agreed | Required | coordinate with users |

---

## Architecture After Cutover

```
EC2 t2.micro (i-0057e3b52162f78f8)
  └── Docker Compose
        ├── web (Flask API)        → connects to RDS via DATABASE_URL
        ├── redis (persistence)    → local Docker, RDB snapshots enabled
        ├── reverse-proxy (nginx)
        └── certbot (TLS profile)

RDS db.t4g.micro  ←  sg-rds allows :5432 from sg-0edf5ab745a438dd2 only
  └── PostgreSQL 16, 20 GB gp3
  └── Backups: daily, 7-day retention
  └── Multi-AZ: false (free tier)
  └── Publicly accessible: false

CloudWatch Alarm: StatusCheckFailed_System >= 1 (2 periods) → EC2 recover
```

---

## Phase 1 — Completed (no prod impact)

Phase 1 tasks were completed without touching prod services:

1. **Terraform RDS config** — added to `infra/api/main.tf`:
   - `aws_db_subnet_group.prod` (default VPC subnets)
   - `aws_security_group.rds` (port 5432 from EC2 SG only)
   - `aws_db_instance.prod` (db.t4g.micro, PG16, 20 GB gp3)
   - `aws_cloudwatch_metric_alarm.ec2_status_check` (auto-recovery)
   - Output: `rds_endpoint`

2. **Migration script** — `scripts/migrate-to-rds.sh`:
   - Reads credentials from EC2 `.env.prod`
   - Runs `pg_dump --format=custom` inside the Docker db container
   - Restores to RDS via `pg_restore`
   - Verifies row counts for key tables

3. **docker-compose.prod.yml** — `db` service commented out with rollback instructions

4. **Redis persistence** — `command: redis-server --save 300 5 --save 60 1000`

---

## Phase 2 — Cutover (Requires Human Approval)

> **Estimated downtime:** 5–15 minutes (pg_dump + restore is fast for small datasets).
> **Rollback time:** < 2 minutes (uncomment `db` service, update DATABASE_URL, restart).

### Step 1: Apply Terraform (creates RDS instance)

```bash
cd /path/to/auraxis-platform/infra/api

# Review the plan first
terraform plan -var="rds_password=<STRONG_PASSWORD>"

# Apply — this creates the RDS instance (~5–10 min to provision)
terraform apply -var="rds_password=<STRONG_PASSWORD>"

# Note the output
terraform output rds_endpoint
# Example: auraxis-prod.cxxxxxx.us-east-1.rds.amazonaws.com:5432
```

> Store the RDS password in AWS Secrets Manager or SSM Parameter Store. Do NOT commit it.

### Step 2: Verify RDS is reachable from EC2

```bash
# Via SSM session on the EC2:
psql -h <rds-endpoint> -U auraxis -d postgres -c "SELECT version();"
```

### Step 3: Open maintenance window

- Post notice on any user-facing status channel.
- Ideal time: low-traffic period (nights/weekends).

### Step 4: Run migration script

```bash
# Via SSM session on EC2:
sudo bash /opt/auraxis/scripts/migrate-to-rds.sh \
  --rds-endpoint <rds-endpoint-from-terraform-output>
```

The script will:
- Dump current Postgres to `/tmp/auraxis_pg_dump_<timestamp>.dump`
- Restore to RDS
- Verify row counts across key tables
- Print cutover instructions

### Step 5: Update `.env.prod` on EC2

```bash
# Via SSM:
# Edit /opt/auraxis/.env.prod and replace DB_* vars with:
DATABASE_URL=postgresql://auraxis:<password>@<rds-endpoint>:5432/auraxis

# Comment out or remove:
# DB_HOST=db
# DB_PORT=5432
# DB_NAME=...
# DB_USER=...
# DB_PASS=...
# POSTGRES_DB=...
# POSTGRES_USER=...
# POSTGRES_PASSWORD=...
```

### Step 6: Deploy updated docker-compose.prod.yml

```bash
# Pull latest compose file (with db service commented out)
cd /opt/auraxis
git pull origin master  # or copy from CI artifact

# Restart only the web service — redis and nginx stay up
docker compose -f docker-compose.prod.yml up -d --no-deps web
```

### Step 7: Verify health

```bash
# Health check endpoint
curl -s https://api.auraxis.com.br/healthz | python3 -m json.tool

# Watch logs for 15 minutes
docker compose -f docker-compose.prod.yml logs -f web 2>&1 | head -100

# Verify RDS connections in logs (should see "database connected" or similar)
```

### Step 8: Stop the old db container

Once confirmed healthy for >= 15 minutes:

```bash
# Stop (do NOT remove yet — keep for 7 days)
docker compose -f docker-compose.prod.yml stop db

# Backup volume to S3 before removing
docker run --rm \
  -v auraxis_pgdata_prod:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/pgdata_prod_$(date +%Y%m%d).tar.gz /data

aws s3 cp pgdata_prod_$(date +%Y%m%d).tar.gz \
  s3://auraxis-backups/postgres-volumes/ \
  --sse AES256

# After 7 days — remove volume
docker volume rm auraxis_pgdata_prod
```

---

## Rollback Procedure

If anything goes wrong before or after Step 8:

```bash
# 1. Uncomment the 'db' service in docker-compose.prod.yml on EC2
# 2. Revert /opt/auraxis/.env.prod to the original DB_* variables
# 3. Restart the stack
docker compose -f docker-compose.prod.yml up -d

# 4. Verify health
curl -s https://api.auraxis.com.br/healthz
```

The pgdata_prod Docker volume is untouched until Step 8, so rollback is lossless for any writes between Phase 1 and Step 7.

> **Note:** Any writes committed to RDS after Step 6 and before rollback will NOT be in the Docker volume. Plan maintenance window accordingly.

---

## RDS Disaster Recovery

| Scenario | Recovery |
|:---------|:---------|
| EC2 instance failure | CloudWatch alarm triggers EC2 `recover` action automatically |
| RDS instance failure | RDS automated restart within ~1–2 min (single-AZ) |
| Data corruption | Restore from automated backup: `aws rds restore-db-instance-to-point-in-time` |
| Accidental deletion | `deletion_protection = true` prevents accidental `terraform destroy` |
| Region outage | Manual: restore final snapshot to new region |

### Point-in-Time Restore

```bash
# List available restore window
aws rds describe-db-instances \
  --db-instance-identifier auraxis-prod \
  --query "DBInstances[0].{LatestRestorableTime:LatestRestorableTime,EarliestRestorableTime:EarliestRestorableTime}"

# Restore to a point in time
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier auraxis-prod \
  --target-db-instance-identifier auraxis-prod-restored \
  --restore-time <ISO8601-timestamp>
```

### From Final Snapshot

```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier auraxis-prod-recovered \
  --db-snapshot-identifier auraxis-prod-final-snapshot
```

---

## Post-Cutover Checklist

- [ ] RDS provisioned and reachable from EC2
- [ ] Migration script ran without row count mismatches
- [ ] `.env.prod` updated with `DATABASE_URL` pointing to RDS
- [ ] docker-compose.prod.yml deployed with `db` service commented out
- [ ] `GET /healthz` returns 200 with database connection OK
- [ ] No errors in web container logs for 15 min
- [ ] Old db container stopped
- [ ] pgdata_prod volume backed up to S3
- [ ] CloudWatch alarm `auraxis-prod-ec2-status-check-failed` visible in AWS console
- [ ] GitHub issue #858 status set to Done

---

## Monitoring After Cutover

| Metric | Where | Alert Threshold |
|:-------|:------|:----------------|
| RDS CPU | CloudWatch → RDS → CPUUtilization | > 80% for 10 min |
| RDS Free Storage | CloudWatch → RDS → FreeStorageSpace | < 2 GB |
| RDS DB Connections | CloudWatch → RDS → DatabaseConnections | > 80 |
| EC2 StatusCheckFailed | CloudWatch Alarm (auto-created by Terraform) | >= 1 for 2 periods |
| API health | https://api.auraxis.com.br/healthz | non-200 |

---

## Related Files

| File | Purpose |
|:-----|:--------|
| `infra/api/main.tf` (platform repo) | Terraform RDS + CloudWatch alarm resources |
| `infra/api/variables.tf` (platform repo) | `rds_password` variable |
| `infra/api/outputs.tf` (platform repo) | `rds_endpoint` output |
| `scripts/migrate-to-rds.sh` | Automated dump/restore/verify script |
| `docker-compose.prod.yml` | Prod compose with db service commented out |
