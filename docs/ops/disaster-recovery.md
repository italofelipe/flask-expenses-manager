# Disaster Recovery Runbook — Auraxis API

**Last updated:** 2026-04-12
**Owner:** Platform / Infra
**Issue:** INF-2 (#962)

---

## 1. Infrastructure Overview

| Component | Detail |
|:----------|:-------|
| EC2 instance | `i-0057e3b52162f78f8` |
| Elastic IP | `100.49.10.188` |
| OS | Amazon Linux 2023 |
| Runtime | Docker Compose (nginx, web x3, redis, postgres) |
| Remote access | AWS SSM only (no SSH) |
| TLS | Let's Encrypt via certbot (Docker volume `auraxis_letsencrypt`) |
| Database | PostgreSQL 16 in Docker (`auraxis-db-1`) |
| PG user | `flaskuser` |
| PG database | `flaskdb` |
| Env file | `/opt/auraxis/.env.prod` |

## 2. Backup Strategy

### Automated Daily Backup

| Item | Value |
|:-----|:------|
| Script | `/opt/auraxis/scripts/backup-db-to-s3.sh` |
| Schedule | Daily at 02:00 UTC (cron) |
| S3 bucket | `s3://auraxis-db-backups/daily/` |
| Format | `pg_dump` compressed (`.sql.gz`) |
| Retention | 30 days (S3 lifecycle rule) |

### Manual Backup (ad-hoc)

```bash
# Via SSM Session
aws ssm start-session --target i-0057e3b52162f78f8

# Inside EC2
source /opt/auraxis/.env.prod
docker exec auraxis-db-1 pg_dump -U flaskuser -d flaskdb | gzip > /tmp/auraxis-manual-$(date +%Y%m%d-%H%M%S).sql.gz
aws s3 cp /tmp/auraxis-manual-*.sql.gz s3://auraxis-db-backups/manual/
```

## 3. Restore Procedure

### 3.1 Restore from S3 Backup

```bash
# 1. Connect via SSM
aws ssm start-session --target i-0057e3b52162f78f8

# 2. Download latest backup
aws s3 ls s3://auraxis-db-backups/daily/ --recursive | sort | tail -1
aws s3 cp s3://auraxis-db-backups/daily/<LATEST_FILE> /tmp/restore.sql.gz

# 3. Stop application containers (keep DB running)
cd /opt/auraxis
docker compose stop web nginx redis

# 4. Restore
gunzip -c /tmp/restore.sql.gz | docker exec -i auraxis-db-1 psql -U flaskuser -d flaskdb

# 5. Restart stack
docker compose up -d

# 6. Verify
docker compose ps
curl -s http://localhost:5000/health | python3 -m json.tool
```

### 3.2 Full Instance Rebuild

If the EC2 instance is lost:

1. Launch new Amazon Linux 2023 instance in the same VPC/subnet
2. Associate Elastic IP `100.49.10.188`
3. Attach IAM instance profile with SSM permissions
4. Install Docker + Docker Compose
5. Clone the repo: `git clone git@github.com:italofelipe/auraxis-api.git /opt/auraxis`
6. Restore `.env.prod` from Secrets Manager or manual reconstruction
7. Run `docker compose up -d`
8. Restore DB from S3 (see 3.1 above, steps 2-6)
9. Restore TLS certs: `docker run --rm -v auraxis_letsencrypt:/etc/letsencrypt certbot/certbot renew --force-renewal`
10. Verify: `curl -s https://api.auraxis.com.br/health`

## 4. TLS Certificate Recovery

Certificates are managed by certbot and stored in Docker volume `auraxis_letsencrypt`.

```bash
# Force renewal
docker run --rm \
  -v auraxis_letsencrypt:/etc/letsencrypt \
  -v auraxis_acme:/var/www/certbot \
  certbot/certbot renew --force-renewal

# Reload nginx to pick up new certs
docker exec auraxis-nginx-1 nginx -s reload

# Verify expiry
echo | openssl s_client -connect api.auraxis.com.br:443 -servername api.auraxis.com.br 2>/dev/null | openssl x509 -noout -dates
```

**Auto-renewal:** certbot renew runs via cron or Docker entrypoint. If certificates expire, the manual force-renewal above recovers them.

## 5. PostgreSQL Operations

### Check slow query log

```bash
docker exec auraxis-db-1 psql -U flaskuser -d flaskdb -c "SHOW log_min_duration_statement;"
# Expected: 500 (ms) — enabled 2026-04-12
```

### Check indexes

```bash
docker exec auraxis-db-1 psql -U flaskuser -d flaskdb -c "\di+"
```

### Reset a stuck migration

```bash
source /opt/auraxis/.env.prod
docker exec auraxis-db-1 psql -U flaskuser -d flaskdb -c "SELECT * FROM alembic_version;"
# If stuck, manually set:
# UPDATE alembic_version SET version_num = '<target_revision>';
```

## 6. Recovery Targets

| Metric | Target | Justification |
|:-------|:-------|:--------------|
| **RPO** (Recovery Point Objective) | 24 hours | Daily backups at 02:00 UTC |
| **RTO** (Recovery Time Objective) | 2 hours | Manual restore from S3 + Docker rebuild |

### Improving RPO

To reduce RPO below 24h, enable WAL archiving to S3:
1. Set `archive_mode = on` and `archive_command` in PG config
2. Ship WAL segments to `s3://auraxis-db-backups/wal/`
3. This enables point-in-time recovery (PITR)

## 7. Monitoring and Alerts

| Check | Mechanism |
|:------|:----------|
| Health endpoint | `GET /health` — returns 200 with component status |
| Backup success | Check S3 bucket for today's file: `aws s3 ls s3://auraxis-db-backups/daily/ | grep $(date +%Y%m%d)` |
| TLS expiry | `openssl s_client` check (see section 4) |
| Disk space | `docker system df` on EC2 |

## 8. Contacts

| Role | Contact |
|:-----|:--------|
| PO / Infra owner | Italo Chagas |
| AWS account | auraxis production |
| Domain registrar | Route53 (auraxis.com.br) |
