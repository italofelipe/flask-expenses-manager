# Auraxis Runbook (DEV/PROD)

Este documento descreve como operar a aplicacao em producao e desenvolvimento (AWS EC2 + Docker Compose), incluindo deploy, backup/restore, TLS, observabilidade e resposta a incidentes.

Regra de ouro:
- Se houver duvida, rode primeiro o checklist automatizado `scripts/aws_validate_i16.py`.

## Ambientes

PROD
- Dominio: `https://api.auraxis.com.br`
- Health: `https://api.auraxis.com.br/healthz`

DEV
- Dominio: `http://dev.api.auraxis.com.br` (HTTP-only por enquanto)
- Health: `http://dev.api.auraxis.com.br/healthz`

## Checklist Rapido (sempre antes/depois de mudancas)

1) Validacao completa:
```bash
./.venv/bin/python scripts/aws_validate_i16.py --profile auraxis-admin --region us-east-1
```

2) Health check manual:
```bash
curl -fsS https://api.auraxis.com.br/healthz
curl -fsS http://dev.api.auraxis.com.br/healthz
```

## Deploy (sem SSH) via SSM

O deploy via SSM aplica um `git checkout` do ref desejado na instancia, renderiza Nginx por ambiente e reinicia o compose. Ao final, valida `/healthz`.

Comandos:

DEV:
```bash
./.venv/bin/python scripts/aws_deploy_i6.py --profile auraxis-admin --region us-east-1 deploy --env dev --git-ref origin/master
```

PROD:
```bash
./.venv/bin/python scripts/aws_deploy_i6.py --profile auraxis-admin --region us-east-1 deploy --env prod --git-ref origin/master
```

Status do deploy (ref atual e ultimo ref "previous" para rollback):
```bash
./.venv/bin/python scripts/aws_deploy_i6.py --profile auraxis-admin --region us-east-1 status --env prod
./.venv/bin/python scripts/aws_deploy_i6.py --profile auraxis-admin --region us-east-1 status --env dev
```

Rollback (para o ref anterior bem sucedido, por instancia):
```bash
./.venv/bin/python scripts/aws_deploy_i6.py --profile auraxis-admin --region us-east-1 rollback --env prod
./.venv/bin/python scripts/aws_deploy_i6.py --profile auraxis-admin --region us-east-1 rollback --env dev
```

Notas:
- O estado do deploy fica em `/var/lib/auraxis/deploy_state.json` na instancia.
- DEV renderiza Nginx em HTTP; PROD renderiza Nginx em TLS usando `deploy/nginx/default.tls.conf`.

## TLS (PROD)

Emissao inicial:
- Script: `scripts/request_tls_cert.sh` (webroot, certbot container)

Renovacao automatica:
- Script: `scripts/renew_tls_cert.sh`
- systemd:
  - `deploy/systemd/auraxis-certbot-renew.service`
  - `deploy/systemd/auraxis-certbot-renew.timer`
- Instalacao via SSM:
```bash
./.venv/bin/python scripts/aws_tls_renew_i15.py --profile auraxis-admin --region us-east-1 install --env prod
```

Validacao (dry-run):
```bash
./.venv/bin/python scripts/aws_tls_renew_i15.py --profile auraxis-admin --region us-east-1 run-once --env prod --dry-run
```

## Backups PostgreSQL (S3) e Restore Drill

Bucket:
- Default: `auraxis-backups-765480282720`

Setup (bucket + lifecycle + policy + IAM access via role de instancia):
```bash
./.venv/bin/python scripts/aws_backups_s3.py --profile auraxis-admin --region us-east-1 setup
```

Backup on-demand:
```bash
./.venv/bin/python scripts/aws_backups_s3.py --profile auraxis-admin --region us-east-1 backup --env prod
./.venv/bin/python scripts/aws_backups_s3.py --profile auraxis-admin --region us-east-1 backup --env dev
```

Restore drill (nao-destrutivo):
```bash
./.venv/bin/python scripts/aws_backups_s3.py --profile auraxis-admin --region us-east-1 restore-drill
```

## Observabilidade (CloudWatch)

Log groups esperados:
- `/auraxis/prod/containers`
- `/auraxis/dev/containers`

Canary:
- Route53 health checks: PROD HTTPS/443, DEV HTTP/80
- Alarmes CloudWatch: `auraxis-health-prod`, `auraxis-health-dev`

Validacao rapida:
```bash
./.venv/bin/python scripts/aws_validate_i16.py --profile auraxis-admin --region us-east-1 --target route53 --target logs
```

## Firewall host (UFW)

Aplicacao via SSM (mantem SSM funcionando, nao abre SSH):
```bash
./.venv/bin/python scripts/aws_ufw_i8.py --profile auraxis-admin --region us-east-1 apply --env prod --execute
./.venv/bin/python scripts/aws_ufw_i8.py --profile auraxis-admin --region us-east-1 apply --env dev --execute
```

Status:
```bash
./.venv/bin/python scripts/aws_ufw_i8.py --profile auraxis-admin --region us-east-1 status --env prod --print-output
./.venv/bin/python scripts/aws_ufw_i8.py --profile auraxis-admin --region us-east-1 status --env dev --print-output
```

## Custos (Budget guardrails)

IMPORTANTE:
- Budgets nao travam gasto automaticamente. Eles alertam.
- Para o teto de ~R$70/mes, usamos um limite conservador em USD (default: USD 10).

Aplicar/atualizar budget + anomaly subscription:
```bash
./.venv/bin/python scripts/aws_cost_guardrails_i5.py --profile auraxis-admin --region us-east-1 --usd-limit 10 --email felipe.italo@hotmail.com --enable-anomaly-detection
```

## Incidentes (playbook minimo)

Sintomas comuns e respostas:

1) API fora do ar (5xx / timeout)
- Rodar checklist `aws_validate_i16.py`
- Verificar alarmes: `auraxis-health-prod` / `auraxis-health-dev`
- Se o deploy recente quebrou: executar rollback do ambiente afetado

2) Certificado expirando / HTTPS falhando
- Rodar `aws_tls_renew_i15.py run-once --dry-run` primeiro
- Rodar `aws_tls_renew_i15.py run-once` (sem dry-run) e validar `/healthz`

3) Necessidade de restore
- Executar restore drill para validar ferramenta
- Em caso de restore real, documentar o plano de RTO/RPO e executar em janela

