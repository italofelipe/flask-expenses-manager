# Threat Model (STRIDE + Abuse Cases)

Updated at: 2026-02-11  
Scope: REST, GraphQL, auth, wallet/investments, CI/CD and AWS runtime.

## 1) System context
- Clients: Postman/Frontend/Web app.
- API: Flask (`/auth`, `/user`, `/transactions`, `/wallet`, `/graphql`).
- Data store: PostgreSQL (DEV/PROD) and SQLite for tests.
- External dependency: BRAPI.
- Infra: AWS EC2 + Nginx + Docker Compose.

## 2) Critical assets
- User credentials (`password`, JWTs, refresh context/JTI).
- Financial data (transactions, wallet, operations, valuation).
- Secrets (app keys, DB credentials, BRAPI token, CI tokens).
- Audit trail / security evidence.
- CI/CD trust chain (GitHub Actions, Sonar, dependency updates).

## 3) Trust boundaries
- Public internet -> Nginx reverse proxy.
- Nginx -> Flask app container.
- Flask -> DB.
- Flask -> BRAPI.
- EC2 runtime -> AWS IAM/SSM/Secrets Manager.
- GitHub PR contributors -> CI pipeline and artifacts.

## 4) STRIDE matrix (high-level)

| STRIDE | Main threat | Current controls | Residual risk |
|---|---|---|---|
| Spoofing | token abuse, credential stuffing | JWT checks, lockout progressivo, rate limit | Médio |
| Tampering | payload manipulation, query abuse | schema validation, GraphQL guards, input normalization | Médio |
| Repudiation | sensitive actions without evidence | audit trail + persistence option | Médio |
| Information Disclosure | exception leaks, sensitive fields in responses | response sanitization, internal error redaction, CORS/headers | Médio |
| Denial of Service | brute-force, high-cost queries, oversized payloads | rate limit, body cap, GraphQL depth/complexity | Médio |
| Elevation of Privilege | cross-user resource access | authz by resource in GraphQL + ownership checks in REST | Médio |

## 5) Abuse cases (priority)
1. Credential stuffing across `/auth/login` and GraphQL `login`.
2. Cross-tenant reference attempt (`tagId/accountId/creditCardId`) in transaction mutation.
3. Injection of malformed ticker/payload from BRAPI dependency surface.
4. Secret leak from runtime configuration/files or CI logs/artifacts.
5. Query cost abuse via nested GraphQL operations.

## 6) Risk acceptance criteria

### P0 (non-negotiable)
- No critical/blocker vulnerabilities open in Sonar.
- No leaked secrets in repository history or PR diffs.
- No endpoint returning stacktrace/internal exception in production mode.
- Auth endpoints with active brute-force controls and rate limit.

### P1 (required before broad public exposure)
- Audit trail persistent with request correlation.
- Secrets sourced from cloud manager in production (no `.env` as source of truth).
- GraphQL private operations protected by transport + resolver ownership checks.

### P2 (continuous hardening)
- Threat model review every significant domain release.
- Incident runbooks for auth lockout, provider outage and Redis/rate-limit degradation.
- Security regression checks preserved in CI and pre-commit.

## 7) Mitigation backlog linkage
- `S4-10`: distributed rate limit and operational observability.
- `S5-02`: persistent audit + retention/search.
- `S5-03`: deeper GraphQL resource authorization.
- `S5-05`: cloud secrets source of truth + rotation.
- `S5-06`: advanced anti-account-takeover signals.
- `S1`: AWS hardening baseline (SG/NACL/IMDSv2/patching).

## 8) Review cadence
- Revisit this document at end of each major block (D/E/security) or when:
  - new external integrations are added;
  - auth model changes;
  - deployment topology changes (e.g., RDS, Redis, multi-instance).
