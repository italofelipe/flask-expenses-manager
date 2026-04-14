# MVP-1 Hardening Strategy

**Updated at:** 2026-04-14
**Scope:** Security posture, API hygiene, and architectural decisions post-MVP-1 launch.

---

## Overview

This document records the decisions, rationale, and execution plan for all H-prefixed
hardening issues. Each section maps to a GitHub issue and captures the chosen approach
as an authoritative product/engineering decision.

---

## H-P5.3 — Session management policy (issue #841)

### Decision: single-session is intentional

The current implementation enforces **single-session** via `User.current_jti` and
`User.refresh_token_jti` columns. A successful login on any device immediately
invalidates any previously issued access + refresh token pair.

**This is intentional product policy, not a limitation.**

#### Rationale

- For MVP-1 with a small user base and a single-core EC2 instance, the operational
  complexity of multi-device session management outweighs the benefit.
- Single-session is a stronger security posture by default: a compromised refresh token
  self-heals when the legitimate user next logs in.
- Multi-device sessions require a `user_sessions` table, token families with rotation,
  and a "connected devices" UI — all deferred to a post-MVP-2 milestone.

#### Implementation notes

- `User.current_jti` tracks the active access token JTI. Any token with a different
  JTI is considered revoked (see `app/extensions/jwt_callbacks.py`).
- `User.refresh_token_jti` tracks the refresh token JTI with replay-attack protection
  (see `app/controllers/auth/refresh_token_resource.py`).
- Logout explicitly clears both JTI fields and the httpOnly refresh cookie.
- When a session is displaced (login on another device), the previous token's revocation
  callback returns `SESSION_DISPLACED` error code so clients can show a targeted message.

#### Frontend contract

When a request fails with `error_code: "SESSION_DISPLACED"`, the client **must** display:

> "Sua sessão foi encerrada porque você entrou em outro dispositivo."

For `error_code: "SESSION_REVOKED"`, the client displays:

> "Sua sessão foi encerrada. Faça login novamente."

#### Future: multi-device (post-MVP-2)

If multi-device is ever adopted, the migration path is:

1. Create `user_sessions` table (`id`, `user_id`, `device_id`, `refresh_jti`,
   `ip`, `user_agent`, `last_active_at`, `revoked_at`)
2. Replace `User.current_jti` / `User.refresh_token_jti` with per-session records
3. Add `GET /user/sessions` and `DELETE /user/sessions/{session_id}` endpoints
4. Add "Dispositivos conectados" screen in web/app

---

## H-P5.2 — Normalizar endpoints de transações (issue #840)

### Decision: consolidate REST surface, add sunset headers

See the dedicated section in `docs/wiki/MVP-1-Transacoes-Tecnico.md` and issue #840
for the full breakdown. Summary of decisions:

- `GET /transactions` is the canonical collection endpoint (with query param filters)
- `GET /transactions/list` is deprecated with `Sunset` + `Deprecation` headers
- `GET /transactions/expenses` is deprecated; use `GET /transactions?type=expense`
- `PATCH /transactions/{id}` is the canonical partial-update method
- `PUT /transactions/{id}` is deprecated with sunset header
- Query params are normalized: `start_date` / `end_date` everywhere

**Status:** Pending implementation.

---

## H-P5.1 — Resolver dualidade REST + GraphQL (issue #839)

### Decision: REST canonical, GraphQL read-only per domain

| Domain | Owner | GraphQL role |
|--------|-------|--------------|
| Auth | REST-only | Mutations deprecated (compat only) |
| Transactions | REST canonical | Read queries only |
| Goals | REST canonical | Read queries only |
| Wallet | REST canonical | Read queries only |
| Dashboard | REST-only | Not exposed |
| User profile | REST canonical | Read queries only |

**Status:** Pending implementation.

---

## H-P4.1 — Migração Flask → FastAPI fase 0 (issue #837)

### Decision: coexistence via nginx routing

Follow `tech_debt/X3_phase0_execution_plan.md`. First two routes to migrate:

1. `GET /healthz` — trivial, validates coexistence infrastructure
2. `GET /dashboard/overview` — read-only, high frequency, good migration candidate

**Status:** BLOCKED (awaiting infrastructure decision and endpoint normalization from
H-P5.2 to land first).
