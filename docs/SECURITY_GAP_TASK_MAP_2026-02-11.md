# Security Gap Map -> TASKS Backlog (Round 2)

Updated at: 2026-02-11  
Scope: full reassessment of `app/`, security config, container and dependency baseline.

## Objective
Map current, still-open security findings into actionable backlog tasks in `TASKS.md` (`S6-01..S6-12`).

## Findings to backlog mapping

| Finding ID | Severity | Gap | Evidence | Backlog task |
|---|---|---|---|---|
| R2-01 | High | Mass assignment in transaction update path | `app/controllers/transaction_controller.py:536` | `S6-01` |
| R2-02 | High | Writable `user_id` in transaction input schema | `app/schemas/transaction_schema.py:16` | `S6-02` |
| R2-03 | High | Missing ownership validation for `tag/account/credit_card` in REST transaction writes | `app/controllers/transaction_controller.py:333`, `app/controllers/transaction_controller.py:384` | `S6-03` |
| R2-04 | High | Exception/internal detail leakage in API responses | `app/controllers/transaction_controller.py:362`, `app/controllers/user_controller.py:372`, `app/controllers/wallet_controller.py:786` | `S6-04` |
| R2-05 | High | GraphQL registration bypasses REST security validation parity | `app/graphql/schema.py:854`, `app/schemas/user_schemas.py:31` | `S6-05` |
| R2-06 | Medium | Account enumeration vectors in register/login behavior | `app/controllers/auth_controller.py:110`, `app/services/login_attempt_guard_service.py:136` | `S6-06` |
| R2-07 | Medium | Login guard not distributed | `app/services/login_attempt_guard_service.py:61` | `S6-07` |
| R2-08 | Medium | Permissive defaults on missing env (`DEBUG`) | `config/__init__.py:21`, `config/__init__.py:49` | `S6-08` |
| R2-09 | Medium | Audit retention sweep in request path | `app/extensions/audit_trail.py:117`, `app/extensions/audit_trail.py:174` | `S6-09` |
| R2-10 | Medium | Known CVEs in runtime dependencies | `requirements.txt:6`, `requirements.txt:19` | `S6-10` |
| R2-11 | Low | Prod container runs as root and includes non-runtime stack | `Dockerfile.prod:1`, `Dockerfile.prod:14` | `S6-11` |
| R2-12 | Low | Public docs exposure policy not restricted in prod | `docker-compose.prod.yml:41`, `app/middleware/auth_guard.py:27` | `S6-12` |

## Recommended execution order
1. `S6-01`, `S6-02`, `S6-03`, `S6-04`, `S6-05`
2. `S6-06`, `S6-07`, `S6-08`, `S6-09`
3. `S6-10`, `S6-11`, `S6-12`
