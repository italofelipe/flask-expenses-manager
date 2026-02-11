# OWASP S3 Checklist (Working Sheet)

Updated at: 2026-02-10
Status scale: `PASS`, `PARTIAL`, `FAIL`, `N/A`.

## API Top 10 Checklist

| Control | Status | Evidence | Action Owner | Next Action |
|---|---|---|---|---|
| API1 - Object-level authorization enforced in all user-owned resources | PARTIAL | Ownership checks present in multiple controllers; missing consolidated matrix tests | Backend | Add endpoint-level authorization tests by resource type |
| API2 - Authentication and token lifecycle hardened | PARTIAL | JWT issuance/revocation present; no explicit rotation/runbook evidence in checklist | Backend/SRE | Add secret rotation policy + token/session hardening checks |
| API3 - Property-level authorization and input field constraints | PARTIAL | Marshmallow validation present; no explicit field-level authorization matrix | Backend | Create allowed-fields matrix per update endpoint |
| API4 - Resource consumption controls (rate/quotas/timeouts) | PARTIAL | Rate-limit baseline ativo e GraphQL com limites de profundidade/complexidade/tamanho/operações (`app/middleware/rate_limit.py`, `app/graphql/security.py`) | Backend | Endurecer quotas por ambiente e adicionar storage distribuído (Redis) |
| API5 - Function-level authorization boundaries documented/tested | PARTIAL | Auth guard + resolver auth exist; no explicit operation policy map | Backend | Add policy map and negative tests |
| API6 - Sensitive business flow abuse protections | PARTIAL | Fluxos críticos com throttling base (auth e transações) via regras dedicadas de rate-limit | Backend | Adicionar heurísticas de abuso, lock progressivo e observabilidade de anomalia |
| API7 - SSRF and outbound request controls | PARTIAL | External provider call exists; no explicit allowlist/policy doc | Backend/SRE | Add outbound policy and validation |
| API8 - Security misconfiguration controls | PARTIAL | TLS + baseline de limites GraphQL; faltam hardening de produção e matriz formal de configuração segura | SRE | Complete hardening controls + evidence |
| API9 - API inventory and lifecycle management | PARTIAL | Inventory started in `OWASP_S3_INVENTORY.md` | Backend | Tie inventory to owners and CI evidence |
| API10 - Safe consumption of third-party APIs | PARTIAL | BRAPI integration has resilience; needs stricter trust/validation policy | Backend | Add external response validation policy |

## ASVS High-Level Checklist

| ASVS Area | Status | Evidence | Next Action |
|---|---|---|---|
| V1 Architecture and threat model | FAIL | No formal threat model artifact | Produce architecture threat model document |
| V2 Authentication | PARTIAL | JWT auth implemented | Add authentication hardening checklist |
| V3 Session management | PARTIAL | JTI revocation exists | Add session abuse controls and tests |
| V4 Access control | PARTIAL | Per-resource checks in many endpoints | Complete authorization matrix and negative tests |
| V5 Validation and sanitization | PARTIAL | Schema validation present | Define sanitization strategy and standards |
| V7 Error handling and logging | PARTIAL | Standardized error payload exists | Add sensitive-data redaction and log policy |
| V8 Data protection | PARTIAL | TLS in transit enabled | Add data-at-rest and secret lifecycle checklist |
| V9 Communications | PARTIAL | HTTPS enabled in prod/dev | Add certificate renewal evidence and monitoring |
| V14 Configuration | PARTIAL | Env-driven config + compose profiles | Add secure defaults and config drift checks |

## Exit Criteria (S3)
- Checklist status filled for all controls above.
- Evidence links captured for each control.
- Failing controls mapped to S2/S1 actionable tasks with owners and priorities.
