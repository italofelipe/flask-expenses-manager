# Security Status Report (Vulnerabilities) - 2026-02-13

Este documento consolida o que foi feito (app + infra + CI) no tema vulnerabilidades/seguranca, onde estamos agora, pendencias e recomendacao de proximos passos.

Importante:
- Este relatorio assume o estado do repo em `refactor/wallet-controller-modularization` (HEAD `f921ac8`).
- Para backlog e status oficial, a fonte de verdade continua sendo `TASKS.md`.

## 1) Resumo Executivo

### Status atual (alto nivel)
- **Infra AWS (S1/S1-03)**: baseline de hardening aplicado e validado (sem SSH, SG/NACL/UFW, EBS criptografado, patching SSM, backups S3 e restore drill).
- **Aplicacao (S2..S6)**: baseline de seguranca implementado (rate-limit, CORS por ambiente, security headers, sanitizacao, politica GraphQL, auditoria, hardening de auth, secrets enforcement).
- **CI/Quality Gates (G6..G10 + Sonar)**: pipeline com gates de seguranca/qualidade (Bandit, Gitleaks, pip-audit, Trivy, Snyk condicional, Schemathesis, mutation testing, Sonar policy enforcement).

### Principais riscos remanescentes (P0/P1)
- **Runbook operacional (I9) ausente**: sem um playbook formal de incidentes, restore completo, rotacao/recuperacao, RTO/RPO e validacao recorrente.
- **Observabilidade incompleta (I7)**: metricas/alertas estao ok, mas **faltam logs centralizados** (app + Nginx + docker) e sinais de saude de aplicacao (health + canary + alertas).
- **Governanca GitHub (G11)**: branch protection e enforcement central ainda aparece como `Todo` em `TASKS.md` (na pratica, foi configurado manualmente, mas precisa estar refletido e/ou automatizado para evitar drift).
- **Banco em container na mesma VM (I4)**: e uma escolha aceitavel para budget baixo, mas e um risco operacional (falha da VM == app + DB). Backups mitigam, mas nao eliminam indisponibilidade.

## 2) O que foi feito (Infra / AWS) - S1

### Ambientes
- PROD: EC2 `i-0057e3b52162f78f8`
- DEV: EC2 `i-0bb5b392c2188dd3d`

### DNS e IPs estaveis
- PROD: `api.auraxis.com.br` -> Elastic IP `100.49.10.188`
- DEV: `dev.api.auraxis.com.br` -> Elastic IP `23.21.75.164`

### Hardening de rede (SG / NACL / egress)
- **Security Groups segregados por ambiente** (DEV/PROD).
- **Ingress**: somente `80/443` publico.
- **SSH (22) removido**.
- **Egress**: restrito a `80/443`, DNS e NTP (objetivo: reduzir exfil e superficie de ataque).
- **NACL** dedicado e associado ao subnet alvo.

Scripts (referencia):
- `scripts/aws_s1_hardening.py`
- `scripts/ufw_hardening.sh`

### Acesso administrativo (SSM Session Manager)
- Acesso operacional via SSM (Session Manager), removendo dependencia de SSH.
- Complemento: EventBridge -> SNS para falhas de comandos SSM.

Scripts:
- `scripts/aws_eventbridge_sns_alerts.py`

### Criptografia e disco
- Root volumes criptografados em DEV/PROD (swap + cleanup).

Script:
- `scripts/aws_encrypt_root_volume.py`

### Patching baseline (SSM Maintenance Window)
- Baseline de patching configurado via SSM Maintenance Window.
- DEV: permite reboot se necessario; PROD: sem reboot automatico.
- Logs do patching enviados para CloudWatch Logs (`/auraxis/ssm/patching`).

Script:
- `scripts/aws_patching_s1.py`

### Backups (PostgreSQL) para S3 + restore drill + agendamento
- Bucket S3 hardenizado com:
  - Block Public Access
  - Versioning
  - Lifecycle (inclui noncurrent versions)
  - Policy de HTTPS e SSE (AES256)
- Backup automatizado via SSM MW:
  - `pg_dump` no container `db`, gzip no host, upload com `--sse AES256`
- Restore drill (DEV) para validar integridade e processo.

Script:
- `scripts/aws_backups_s3.py`

### Alertas (SNS + CloudWatch)
- SNS topic `auraxis-alerts` com inscricao de email (felipe.italo@hotmail.com)
- Alarmes:
  - CPU high
  - Status check failed
  - Memory high (CloudWatch Agent)
  - Disk high (CloudWatch Agent)

Scripts:
- `scripts/aws_cloudwatch_agent.py`
- `scripts/aws_observability_i7.py`

## 3) O que foi feito (Aplicacao) - S2..S6 (baseline)

Este bloco endereca OWASP API Top 10 / ASVS no nivel de aplicacao e reduz riscos comuns: auth bypass, brute-force, data leakage, injection, abuso de GraphQL, e falhas de configuracao.

### Autenticacao e protecoes de abuso
- **JWT**: callbacks/erros padronizados e hardening de respostas.
- **Login guard / anti brute-force**: cooldown progressivo e telemetria.
- **Mitigacao de enumeracao** em login/register (comportamento/tempo).

### Validacao, sanitizacao e limites
- Limite global de payload.
- Sanitizacao/normalizacao central para campos textuais.
- Paginacao/endpoints com limites maximos.
- Politica de CORS por ambiente com validacao no startup.

### Headers e superficie HTTP
- Security headers centralizados (HSTS, XFO, XCTO, etc).
- Politica de exposicao de docs por ambiente (quando aplicavel).

### GraphQL hardening
- Deny-by-default para operacoes privadas (auth obrigatoria).
- Limites de:
  - tamanho do payload
  - profundidade
  - complexidade
- Introspecao configuravel por ambiente (desabilitar em PROD por padrao).

### Auditoria / trilha
- Logs estruturados + trilha de auditoria para rotas sensiveis.
- Persistencia opcional + retention e ferramenta operacional para purge.

## 4) O que foi feito (CI/CD e Gates) - Qualidade/Security

### Gates principais
- Lint/format/type-check (mypy) alinhado ao CI.
- Testes + cobertura minima (meta >= 85%).
- Dependency scan: `pip-audit` (quebra build quando CVE conhecido atinge dependencias).
- SAST: Bandit.
- Secret scanning: Gitleaks (pre-commit + CI).
- Container scan: Trivy (HIGH/CRITICAL).
- Snyk (dependencias e container) com actions fixadas (evita supply-chain) e gate condicional.
- Schemathesis (contrato / confiabilidade API) com calibracao para evitar flakiness.
- Mutation testing: Cosmic Ray em escopo critico (custo controlado).
- Sonar: scan + quality gate + enforcement adicional (A ratings).

Scripts auxiliares locais:
- `scripts/run_ci_quality_local.sh`
- `scripts/sonar_local_check.sh`

## 5) Pendencias / Gaps (por prioridade)

### P0 (fazer agora)
1) **I9 - Runbook operacional**:
   - Restore completo (db + app) e teste de RTO/RPO com dados reais (pelo menos mensal).
   - Rotacao de secrets (o que roda, quando, como validar).
   - Incidentes: como agir em vazamento, abuso, picos, indisponibilidade.
2) **I7 - Logs centralizados**:
   - Forward de logs (Nginx, app/gunicorn, docker) para CloudWatch Logs com retention.
   - Alertas baseados em logs (ex.: 5xx spikes, auth failures, rate-limit triggers, errors GraphQL).
3) **G11 - Branch protection / enforcement central**:
   - Garantir que regras do GitHub estejam refletidas no backlog e tenham evidencias do que e exigido (checks required, no force push, PR reviews, etc).

### P1 (logo em seguida)
4) **I6 - Deploy automatico com rollback basico**:
   - Reduz risco humano e padroniza releases (DEV primeiro, depois PROD).
5) **I4/I5 - Estrategia de banco**:
   - Manter DB em container (ok para budget), mas documentar claramente limites e plano de contingencia.
   - Validar se RDS cabe no budget (geralmente nao com folga), e definir criterios de migracao.
6) **Reconciliacao de status em `TASKS.md`**:
   - Existem itens que na pratica ja estao funcionando (TLS etc) mas estao com status parcial.

### P2 (melhorias continuas)
7) Threat model evolutivo (atualizar com novos endpoints/features).
8) Hardening de least-privilege IAM por ambiente (refinar policies por scripts/roles).
9) Canary/healthcheck externo (uptime), mesmo que 24/7 nao seja requisito.

## 6) Recomendacao objetiva: o que fazer em seguida (sequencia)

1) Fechar **I7 (logs centralizados + retention + alertas por erro)**.
2) Implementar **I9 (runbook + restore drill recorrente)**.
3) Fechar **G11** (ou reconciliar com o que ja foi configurado manualmente e garantir enforcement).
4) Depois disso: com base solida, voltar para features (Metas E1..E6) mantendo os gates.

