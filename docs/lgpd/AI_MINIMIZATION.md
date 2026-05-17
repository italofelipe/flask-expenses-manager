# LGPD — AI minimisation & traceability

Issue: [#1258](https://github.com/italofelipe/auraxis-api/issues/1258).
Companion document: [`docs/lgpd/REGISTRY.md`](REGISTRY.md).

This document is the public-facing description of how the Auraxis backend
handles personal data when it generates AI insights. It applies to every
endpoint served by `app.controllers.ai.resources` (spending insights, goal
projection narrative, weekly summary narrative).

## 1. What is minimised before the LLM is called

Before any prompt reaches the model provider, the snapshot that feeds the
prompt is passed through `app.services.ai_lgpd.minimize_prompt_data`. The
helper removes / transforms the following classes of data:

| Class                       | Treatment                                       |
|-----------------------------|-------------------------------------------------|
| Email addresses             | replaced by `[redacted]`                        |
| Full names                  | replaced by `[redacted]` or `usuário`           |
| UUIDs (any 8-4-4-4-12 hex)  | replaced by `[redacted]`                        |
| JWT-like tokens             | replaced by `[redacted]`                        |
| Raw BRL amounts (R$ X,XX)   | replaced by `[redacted]`                        |
| Transaction descriptions    | collapsed to `"item"` (free-text → shape only)  |
| `*_id` keys in any dict     | dropped from the prompt context                 |
| `total_income`/`balance`/…  | bucketed (`<R$100`, `R$1k–R$10k`, …) or `~%`    |

Free-text inputs that come directly from the user (the `user_context` field
on the goal projection endpoint, goal titles) are also passed through
`minimize_text` before they are interpolated into prompts.

The end result: **the LLM never receives an email address, a name, an
internal identifier, a JWT, or a raw monetary value**. It only receives the
*shape* of the financial situation, which is what it needs to produce
useful insights.

## 2. Base legal — consent gate

Every call to one of the three generators is preceded by a call to
`app.services.ai_lgpd.ensure_ai_consent_granted`. The function inspects the
versioned consent log (`Consent` table — see `docs/lgpd/REGISTRY.md`) and
raises `AIConsentRequiredError` (mapped to HTTP **403 AI_CONSENT_REQUIRED**)
when the latest event for `(user_id, kind=ai)` is anything other than
`granted`. Concretely:

- User who never accepted the AI consent → 403
- User who once accepted and later revoked → 403
- User whose latest event is `granted` → request proceeds; the helper also
  returns the consent **version** so it can be stamped on the audit row
  and on the persisted insight.

## 3. Audit trail — `LLMAuditLog`

Every successful LLM call writes a row to `llm_audit_logs` (LGPD registry
entry: `deletion_strategy=DELETE`, `retention_reason=SECURITY`,
`retention_days=90`). The row is redacted at write time:

| Column              | Stored content                                              |
|---------------------|-------------------------------------------------------------|
| `prompt`            | `sha256:<hex>;len:<int>;consent:<version>` — never raw text |
| `response_text`     | `sha256:<hex>;len:<int>;preview:<≤240 chars minimised>`     |
| `prompt_tokens`     | integer                                                     |
| `completion_tokens` | integer                                                     |
| `total_tokens`      | integer                                                     |
| `estimated_cost_usd`| numeric                                                     |
| `latency_ms`        | integer                                                     |
| `model`             | provider model id (e.g. `gpt-4o-mini`)                      |
| `endpoint`          | which generator ran (`spending_insights`, …)                |

The hash is the SHA-256 of the original prompt/response, so a regulator who
holds the original prompt can verify that the recorded row is the right
one — without us retaining the original text. The bounded `preview` is the
first ≤240 characters of the response after `minimize_text`, kept only so
that compliance reviews can confirm the model's tone (no PII echoed).

## 4. Persistent output — `AIInsight`

The insight returned to the user is persisted in `ai_insights`. The model
output itself is what the user sees, so its body is not redacted. The
consent version that covered the generation is recorded on the
``LLMAuditLog`` row written in the same transaction — there is exactly one
audit row per persisted insight, so the LGPD audit chain stays complete
without changing the ``AIInsight`` schema:

```
LLMAuditLog.prompt = "sha256:<hex>;len:<int>;consent:<version>"
```

A follow-up issue is tracked in the PR description to add a dedicated
``consent_version`` column to ``AIInsight`` once the migration plan for the
next sprint lands; until then, joining on user / period via the audit table
provides the same auditability without requiring a migration in this PR.

## 5. Retention

| Entity        | Strategy           | Window          |
|---------------|--------------------|-----------------|
| `AIInsight`   | `DELETE` on erasure| user-account life |
| `LLMAuditLog` | `DELETE` on erasure| 90 days (`SECURITY`) |
| `Consent`     | `ANONYMIZE`        | indefinite (LGPD process evidence) |

These rules are encoded in `app/lgpd/registry.py` and verified by
`tests/lgpd/test_registry.py`. They drive both the export endpoint
(`/user/me/export` — issue #1256) and the deletion service (issue #1257).

## 6. Quick reference for engineers

If you add a new AI-powered endpoint:

1. Call `ensure_ai_consent_granted(user_id)` first thing.
2. Pass any snapshot through `minimize_prompt_data` before the prompt
   builder; pass any free-text user input through `minimize_text`.
3. Use `_log_llm_call(..., consent_version=...)` so the audit row carries
   the consent reference.
4. The consent reference is automatically attached to the
   ``LLMAuditLog.prompt`` marker by ``_log_llm_call(..., consent_version=...)``
   — no extra step is required for new endpoints that follow this pattern.
5. Register the entity in `app/lgpd/registry.py` and add the corresponding
   test in `tests/lgpd/test_registry.py`.
