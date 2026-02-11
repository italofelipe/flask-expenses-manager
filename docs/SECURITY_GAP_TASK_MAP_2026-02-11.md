# Security Gap Map -> TASKS Backlog

Updated at: 2026-02-11  
Scope: codebase review of `app/`, runtime config and current CI/security controls.

## Objective
Consolidate all identified fragilities/vulnerabilities and map each one to an actionable task in `TASKS.md`.

## Findings Summary

| Finding ID | Severity | Gap | Evidence (code/docs) | Backlog task |
|---|---|---|---|---|
| F-01 | High | Internal exception details exposed in API responses | `app/controllers/auth_controller.py`, `app/controllers/user_controller.py`, `app/controllers/wallet_controller.py` retornavam `str(e)` | `S4-01` |
| F-02 | Medium | Debug `print` and traceback leakage in runtime path | `app/middleware/auth_guard.py`, `app/controllers/wallet_controller.py`, `app/__init__.py` | `S4-02` |
| F-03 | Medium | JWT/auth error contract inconsistency across middleware/callbacks/controllers | `app/extensions/jwt_callbacks.py`, `app/middleware/auth_guard.py` | `S4-03` |
| F-04 | High | No explicit global request body size limits for REST routes | Global Flask app config lacks payload cap | `S4-04` |
| F-05 | High | Unbounded/high-cost pagination paths | `app/controllers/user_controller.py` (`limit` sem teto), `app/controllers/wallet_controller.py` (`per_page<=0` retorna tudo) | `S4-05` |
| F-06 | High | Missing centralized sanitization/normalization for text fields | `title`, `description`, `observation`, `notes`, `name` accepted in multiple controllers | `S4-06` |
| F-07 | High | GraphQL private auth model depends on resolver discipline (risk of future endpoint exposure) | `app/controllers/graphql_controller.py` open transport + resolver-level auth in schema | `S4-07` |
| F-08 | Medium | GraphQL introspection exposure policy not defined by env | `app/graphql/security.py` does not control introspection yet | `S4-08` |
| F-09 | Medium | External API trust model incomplete (ticker/input/output hardening) | `app/services/investment_service.py` consumes provider data with minimal schema validation | `S4-09` |
| F-10 | High | Token revocation and rate-limit state are in-memory only | `app/extensions/jwt_callbacks.py`, `app/middleware/rate_limit.py` | `S4-10` |
| F-11 | High | Weak secret fallbacks in non-dev runtime | `config/__init__.py` defaults `SECRET_KEY=dev`, `JWT_SECRET_KEY=super-secret-key` | `S4-11` |
| F-12 | Medium | CORS policy not explicitly configured by environment | Flask app boot has no CORS restrictions layer | `S4-12` |
| F-13 | Medium | Lack of auditable trail for sensitive actions | No central audit logger for login/profile/transaction/wallet operations | `S4-13` |
| F-14 | Low | Legacy/unregistered controller can create drift/confusion | controlador REST legado de ticker removido do código para alinhar superfície real | `S4-14` |
| F-15 | Medium | Security decisions not yet tied to formal threat model | No STRIDE/abuse-case artifact in docs | `S4-15` |
| F-16 | Medium | Dependency CVE checks not enforced in CI | `.github/workflows/ci.yml` lacks dependency security scan step | `S4-16` |

## Already mitigated in current cycle

1. REST/GraphQL rate-limit baseline (`S2.1`):
- `/auth`, `/graphql`, `/transactions`, `/wallet` protected.
- file: `app/middleware/rate_limit.py`

2. GraphQL transport baseline hardening (`S2.2`):
- query size, depth, complexity and operation count guards.
- files: `app/graphql/security.py`, `app/controllers/graphql_controller.py`
- tests: `tests/test_graphql_security.py`

## Recommended execution order (next)

1. `S4-01`, `S4-04`, `S4-05`, `S4-06`, `S4-10` (critical package)
2. `S4-03`, `S4-07`, `S4-11`, `S4-13`
3. `S4-08`, `S4-09`, `S4-12`, `S4-16`
4. `S4-14`, `S4-15`
