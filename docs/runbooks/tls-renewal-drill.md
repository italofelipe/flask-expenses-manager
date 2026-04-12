# TLS Renewal Drill — `api.auraxis.com.br`

**Last updated:** 2026-04-11
**Owner:** Platform Ops
**Cadence:** monthly, first Tuesday 10:30 BRT (15 min)
**Related:** `docs/NGINX_AWS_TLS.md`, `docs/runbooks/disaster-recovery.md`

## Purpose

The production API uses a Let's Encrypt certificate issued via Certbot and
renewed by a cron entry running inside the `certbot` service of
`docker-compose.prod.yml`. The cron entry has never been exercised end-to-end
against the live stack, so we do not have direct evidence that:

- The certbot container can reach ACME from the EC2 host.
- The webroot volume (`/var/www/certbot`) is still mounted correctly.
- Nginx reloads pick up a freshly renewed certificate without downtime.

A `--dry-run` drill validates every step **without issuing a new certificate**
or incrementing the Let's Encrypt issuance counter. It must be run before each
real renewal window to catch breakage early.

## Why `--dry-run`

Certbot's `--dry-run` uses the Let's Encrypt staging environment, which does
not count against the 5-per-week issuance rate limit, does not replace the
live certificate on disk, and still exercises ACME challenge delivery through
the webroot path. If the drill fails, production TLS is untouched.

## Cadence

| Window | Frequency | Execution SLA |
| :--- | :--- | :--- |
| Monthly drill | First Tuesday, 10:30 BRT | ≤ 15 min |
| 30-day pre-expiry drill | ≥ 30 days before expiration | ≤ 15 min |
| Post-incident drill | After any nginx/certbot config change | ≤ 15 min |

Live certificate expiration is surfaced in the ops calendar and in the CloudWatch
alarm (see Observability section below). The first scheduled drill window is
**2026-05-05** — this predates the current certificate expiry (2026-05-19) by
two weeks, leaving room to remediate.

## Drill procedure

All steps assume you are SSM/SSH'd into the production EC2 host and inside the
`/opt/auraxis` working directory.

### 1. Pre-flight checks

```bash
# Confirm the live cert and its expiry date
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm certbot certificates

# Expected: a single certificate for api.auraxis.com.br with
# "VALID: NN days"
```

Record the `VALID: NN days` value in the drill log below.

### 2. Run the dry-run renewal

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm certbot \
  renew --dry-run --non-interactive
```

Expected tail (abridged):

```
Congratulations, all simulated renewals succeeded:
  /etc/letsencrypt/live/api.auraxis.com.br/fullchain.pem (success)
```

If Certbot reports `simulated renewals failed`, STOP and open an incident.
The live cert is still valid; you have time to fix the pipeline before the
next real renewal attempt.

### 3. Validate Nginx reload path

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec reverse-proxy nginx -t
docker compose --env-file .env.prod -f docker-compose.prod.yml exec reverse-proxy nginx -s reload
curl -sI https://api.auraxis.com.br/docs/ | head -1
```

Expected:
- `nginx -t` → `configuration file ... syntax is ok` / `test is successful`
- `nginx -s reload` → no output, exit 0
- `curl` → `HTTP/2 200`

Reload is idempotent — it does not drop in-flight connections, so the drill
is safe during business hours.

### 4. Confirm cron is armed

```bash
crontab -l | grep certbot
```

Expected (single line, 03:00 UTC):

```
0 3 * * * cd /opt/auraxis && docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm certbot renew --quiet && docker compose --env-file .env.prod -f docker-compose.prod.yml exec reverse-proxy nginx -s reload
```

If the line is missing, re-install it (this is the single source of truth for
automated renewal — do NOT rely on systemd timers).

### 5. Log the drill

Append to the drill log table at the bottom of this document.

## Observability

A CloudWatch alarm and an UptimeRobot HTTPS monitor are the two independent
signals that cover TLS health:

- **CloudWatch custom metric `auraxis.tls.days_to_expiry`** → alarm fires at
  `< 21 days`. The metric is published by `scripts/tls_expiry_probe.sh`
  executed daily from the EC2 cron (INF-5). When the alarm fires, run this
  drill immediately and, if successful, let the cron attempt the real renewal
  at 03:00 UTC. If the alarm keeps firing for >24h after a successful drill,
  escalate.
- **UptimeRobot HTTPS keyword monitor** → checks `https://api.auraxis.com.br/healthz`
  every 5 minutes. Will flag a cert-chain failure within minutes of the real
  renewal if something goes wrong.

The drill deliberately does NOT rely on the alarms firing — it is proactive.

## Rollback / Recovery

- **Dry-run fails in ACME step:** check that `/var/www/certbot` is still bind-mounted
  and that TCP 80 is reachable from ACME (SG rule + Route 53 A record for
  `api.auraxis.com.br`). No production impact.
- **Dry-run passes but real renewal fails later:** use the 03:00 cron logs on the
  EC2 host (`journalctl --since "03:00"` or `/var/log/cron`) and certbot's own
  log inside the container (`/var/log/letsencrypt/letsencrypt.log`). While the
  live cert is still valid, re-run step 2 above with the fix applied.
- **Live cert is expired and renewal cannot complete:** follow the nuclear path
  in `docs/NGINX_AWS_TLS.md#issue-tls-certificate` — reissue a fresh cert using
  the `request_tls_cert.sh` script. Expect a brief mixed-content window on the
  API since browsers will reject the old cert chain until Nginx reloads.

## Drill log

Append a row per drill. If you find a regression, record it inline and link to
the incident or PR that resolved it.

| Date | Driver | Cert days remaining before drill | Dry-run result | Nginx reload | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| _pending_ | _owner_ | _NN days_ | _pass/fail_ | _pass/fail_ | First scheduled drill: 2026-05-05 |

## Why this is documented and not yet executed

As of **2026-04-11**, the agent that authored this runbook does not hold
AWS SSM/SSH credentials for the production EC2 host. Live execution is
deferred to the **2026-05-05 drill window** and will be driven by the
platform owner. Once the first drill lands, add the row to the log and
remove this note.
