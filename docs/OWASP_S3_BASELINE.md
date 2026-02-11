# OWASP Baseline (S3)

Updated at: 2026-02-11
Scope: Auraxis API (REST + GraphQL), deployment model (EC2 + Docker + Nginx).

## Goal
Start security execution order defined by product: `S3 -> S2 -> S1`.
This document records the initial OWASP baseline and implementation backlog.

## Method
- Reference sets:
  - OWASP API Security Top 10 (2023)
  - OWASP ASVS (v4.x) high-level controls for API/web backend
- Assessment style:
  - code/documentation review (current repository state)
  - runtime/deployment observations already validated in AWS dev/prod setup

Supporting artifacts:
- `docs/OWASP_S3_INVENTORY.md` (REST/GraphQL attack-surface inventory and OWASP focus map)
- `docs/OWASP_S3_CHECKLIST.md` (working checklist with status/evidence/actions)
- `docs/OWASP_S3_REMEDIATION_PLAN.md` (prioritized remediation roadmap for S2/S1)
- `docs/SECURITY_GAP_TASK_MAP_2026-02-11.md` (fragility-to-task mapping backlog)
- `scripts/security_evidence_check.sh` (automated baseline checks)
- CI artifact: `reports/security/security-evidence.md`

## Baseline Summary
- Current maturity: **partial**.
- Existing positives:
  - JWT auth integrated in most protected endpoints.
  - TLS enabled in production and development domains via Nginx + Certbot.
  - Input validation present in multiple schemas (Marshmallow).
  - CI quality gates with lint/type/test + Sonar checks.
  - Rate-limit baseline ativo para `/auth`, `/graphql`, `/transactions` e `/wallet`.
  - GraphQL com limites de profundidade, complexidade, tamanho de query e operações.
- Main gaps:
  - Rate-limit ainda em baseline in-memory (sem storage distribuído e sem tuning por ambiente).
  - Limites GraphQL ainda sem custo por campo baseado em domínio real.
  - No centralized request sanitization strategy.
  - Incomplete security headers coverage at app/proxy boundaries.
  - Necessidade de expandir evidências OWASP para hardening operacional (S1/S2).

## OWASP API Top 10 (2023) quick status
- API1 Broken Object Level Authorization: **Partial**
  - JWT exists; ownership checks present in several flows.
  - Need full endpoint-by-endpoint authorization matrix.
- API2 Broken Authentication: **Partial**
  - JWT flows implemented.
  - Need stronger token/session controls and secret rotation policy.
- API3 Broken Object Property Level Authorization: **Gap**
  - Need field-level allowlist/hardening audit per update endpoint.
- API4 Unrestricted Resource Consumption: **Partial**
  - Rate-limit baseline implementado; falta endurecimento de quotas e proteção distribuída.
- API5 Broken Function Level Authorization: **Partial**
  - Auth guard exists; require explicit role/policy mapping and tests.
- API6 Unrestricted Access to Sensitive Business Flows: **Partial**
  - Fluxos críticos já têm throttling base; faltam heurísticas de abuso e monitoramento.
- API7 SSRF: **Unknown/Low evidence**
  - External calls exist (market data provider). Need outbound validation/allowlist policy.
- API8 Security Misconfiguration: **Partial**
  - TLS e controles de GraphQL presentes; hardening de infra/app ainda pendente.
- API9 Improper Inventory Management: **Gap**
  - Need inventory of REST/GraphQL operations and security ownership.
- API10 Unsafe Consumption of APIs: **Partial**
  - External provider integration exists; need stricter response validation/fallback policies.

## ASVS-oriented control status (high-level)
- V1 Architecture/Threat Modeling: **Gap**
- V2 Authentication: **Partial**
- V3 Session Management: **Partial**
- V4 Access Control: **Partial**
- V5 Validation/Sanitization: **Partial**
- V7 Error Handling/Logging: **Partial**
- V8 Data Protection/Cryptography: **Partial**
- V9 Communications (TLS): **Done baseline / hardening pending**
- V10 Malicious Code: **Partial**
- V14 Config: **Partial**

## Initial implementation backlog (execution order)
1. S3.1 Security inventory and ownership matrix (REST + GraphQL).
2. S3.2 OWASP checklist as actionable controls with acceptance criteria.
3. S3.3 Security test plan (unit/integration) and CI evidence artifacts.
4. S3.4 Prioritized remediation list feeding S2 (app controls) and S1 (infra controls).

## S3.3 Progress
- Implemented `scripts/security_evidence_check.sh` to assert baseline controls and emit evidence report.
- Integrated CI job `security-evidence` in `.github/workflows/ci.yml`.
- Evidence artifact published in CI as `security-evidence`.

## S3.4 Progress
- Prioritized remediation plan created in `docs/OWASP_S3_REMEDIATION_PLAN.md`.
- Backlog structured by risk/priority and mapped to S2 (app controls) and S1 (infra controls).

## Exit criteria for S3
- Complete OWASP/API checklist with status per control.
- Gap list linked to actionable tickets in `TASKS.md`.
- Security evidence bundle location documented (CI artifacts/docs).
- Clear handoff package to start S2 then S1.
