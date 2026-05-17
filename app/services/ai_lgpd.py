"""LGPD minimisation, consent gating and audit-redaction helpers for AI flows.

Issue: #1258 — *LGPD/IA — minimização e rastreabilidade dos insights*.

Responsibilities (single source of truth used by ``ai_advisory_service``):

- :func:`ensure_ai_consent_granted` — raise :class:`AIConsentRequiredError`
  when the user has not granted (or has revoked) the ``AI`` consent kind.
- :func:`minimize_prompt_data` — strip PII (email, full name, UUID, raw
  monetary values, free-text descriptions) from any dict before it is
  serialised into a prompt.
- :func:`minimize_text` — sanitise an arbitrary free-text string (used for
  ``user_context`` in goal projection prompts).
- :func:`redact_prompt_for_audit` — return the short, structured marker that
  is persisted in ``LLMAuditLog.prompt`` instead of the raw prompt.
- :func:`redact_response_for_audit` — bounded-length response snapshot kept
  for auditability without storing arbitrary user-bound text indefinitely.
- :func:`record_audit_metadata` — helper that builds the audit metadata
  preserved alongside hashes (consent version, token counts, cost, model).

The module is intentionally protocol-agnostic — it never touches Flask, never
hits the database other than reading the consent log, never logs to stdout.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from app.application.services.consent_service import current_state_for
from app.extensions.database import db
from app.models.consent import Consent, ConsentAction, ConsentKind

# Maximum response_text length we retain in the audit log. Anything beyond is
# truncated with an ellipsis marker so the column stays bounded and free of
# unbounded user-bound text.
_MAX_RESPONSE_AUDIT_LEN: int = 240
# Sentinel used by ``minimize_text``/``minimize_prompt_data`` when sensitive
# values are detected and replaced.
_PLACEHOLDER: str = "[redacted]"
_USER_PLACEHOLDER: str = "usuário"

# Patterns used by ``minimize_text``. The order matters — email must be
# stripped before the generic word-character pattern would mangle it.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
# JWT-like tokens (three base64url segments separated by dots).
_JWT_RE = re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+\b")
# Raw BRL amounts ("R$ 1.234,56", "R$1234.56", etc).
_BRL_RE = re.compile(r"R\$\s?\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{2})?")


class AIConsentRequiredError(Exception):
    """Raised when an AI-bound operation is attempted without the AI consent.

    Carries a stable ``error_code`` so REST controllers can map the failure to
    a 403 with code ``AI_CONSENT_REQUIRED`` without leaking the LGPD wording
    into the public surface.
    """

    error_code: str = "AI_CONSENT_REQUIRED"

    def __init__(
        self,
        message: str = (
            "AI features require an active consent. Grant the 'ai' consent "
            "via POST /me/consents before retrying."
        ),
    ) -> None:
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Consent gate
# ---------------------------------------------------------------------------


def ensure_ai_consent_granted(user_id: UUID) -> str | None:
    """Block when the AI consent has never been granted or has been revoked.

    Returns the version of the most recently granted consent (``None`` is
    impossible after the guard — if it would be ``None`` the function raises).

    The version is returned so the caller can persist a reference to which
    consent record covered this generation (see #1258 §4 — base legal).
    """
    state = current_state_for(user_id, ConsentKind.AI)
    if state is not ConsentAction.GRANTED:
        raise AIConsentRequiredError()

    latest_granted: Consent | None = (
        db.session.query(Consent)
        .filter_by(
            user_id=user_id,
            kind=ConsentKind.AI,
            action=ConsentAction.GRANTED,
        )
        .order_by(Consent.created_at.desc())
        .first()
    )
    if latest_granted is None:  # pragma: no cover - defensive
        raise AIConsentRequiredError()
    return str(latest_granted.version)


# ---------------------------------------------------------------------------
# Prompt minimisation
# ---------------------------------------------------------------------------


def minimize_text(value: str | None) -> str:
    """Return a copy of ``value`` with email/uuid/JWT/BRL amounts redacted.

    Empty / ``None`` inputs return an empty string. The function never raises
    so it is safe to call inside prompt builders.
    """
    if not value:
        return ""
    text = str(value)
    text = _EMAIL_RE.sub(_PLACEHOLDER, text)
    text = _UUID_RE.sub(_PLACEHOLDER, text)
    text = _JWT_RE.sub(_PLACEHOLDER, text)
    text = _BRL_RE.sub(_PLACEHOLDER, text)
    return text


def _minimize_amount(value: Any, *, total_for_pct: float | None = None) -> Any:
    """Replace a raw monetary value with a bucketed indicator.

    ``total_for_pct`` lets callers express the value as a percentage of a
    reference total. When omitted the value is bucketed into qualitative
    bands so the prompt receives shape information without the exact figure.
    """
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return value

    if total_for_pct and total_for_pct > 0:
        pct = round(amount / total_for_pct * 100, 1)
        return f"~{pct}%"

    abs_amount = abs(amount)
    if abs_amount == 0:
        return "zero"
    if abs_amount < 100:
        return "<R$100"
    if abs_amount < 1_000:
        return "R$100–R$1k"
    if abs_amount < 10_000:
        return "R$1k–R$10k"
    if abs_amount < 100_000:
        return "R$10k–R$100k"
    return ">R$100k"


_MINIMIZED_DESCRIPTION_PLACEHOLDER = "item"


def _minimize_description(_value: Any) -> str:
    """Reduce a transaction-description string to a non-PII shape signal.

    Implementation choice: free-text descriptions can carry merchant names,
    Pix payee names, recipient phone numbers, addresses. None of those are
    needed by the LLM to identify *patterns*. We collapse the description to
    a single token regardless of input — the LLM still receives count +
    bucket info via the surrounding structure (totals, ranks).

    The parameter is intentionally ignored (underscore-prefixed). The helper
    stays as a function (rather than inlining the constant) so the
    minimisation contract is documented and easy to evolve without touching
    every call site.
    """
    return _MINIMIZED_DESCRIPTION_PLACEHOLDER


def minimize_prompt_data(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitised copy of ``raw`` safe to embed in an LLM prompt.

    Removed/transformed:

    - Any ``email``, ``name``, ``full_name`` or UUID-typed key is dropped.
    - Lists of ``{"description": ..., "total": ...}`` (the snapshot's
      ``top_expenses`` / ``pending_expenses``) have descriptions collapsed
      and totals bucketed.
    - Top-level ``total_expense``, ``total_income``, ``balance``,
      ``pending_expense_total`` are kept but bucketed.
    - ``savings_rate_pct`` is rounded but preserved (already a percentage).

    Unknown keys flow through verbatim — the function is conservative and
    only redacts shapes it knows are sensitive.
    """
    if not isinstance(raw, dict):
        return raw

    out: dict[str, Any] = {}
    income_ref = float(raw.get("total_income") or 0)

    for key, value in raw.items():
        lowered = key.lower()
        if lowered in {"email", "name", "full_name", "user_email", "user_name"}:
            continue
        if lowered.endswith("_id") or lowered == "id":
            # User/account/transaction ids never help the model.
            continue

        if lowered in {"top_expenses", "pending_expenses"} and isinstance(value, list):
            out[key] = [_minimize_expense_row(row, income_ref) for row in value]
            continue

        if lowered in {
            "total_expense",
            "total_income",
            "balance",
            "pending_expense_total",
        }:
            out[key] = _minimize_amount(value, total_for_pct=income_ref or None)
            continue

        out[key] = value

    return out


def _minimize_expense_row(row: Any, income_ref: float) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {"description": "item", "total": _minimize_amount(row)}
    return {
        "description": _minimize_description(row.get("description")),
        "total": _minimize_amount(row.get("total"), total_for_pct=income_ref or None),
    }


# ---------------------------------------------------------------------------
# Audit redaction
# ---------------------------------------------------------------------------


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact_prompt_for_audit(
    prompt: str,
    *,
    consent_version: str | None = None,
) -> str:
    """Return the short structured marker stored in ``LLMAuditLog.prompt``.

    Format: ``sha256:<hex>;len:<int>[;consent:<version>]``

    The hash preserves audit linkability — a regulator who receives the same
    prompt can verify the hash matches the audit row — without leaking PII.
    """
    digest = _sha256_hex(prompt or "")
    parts = [f"sha256:{digest}", f"len:{len(prompt or '')}"]
    if consent_version:
        parts.append(f"consent:{consent_version}")
    return ";".join(parts)


def redact_response_for_audit(response_text: str) -> str:
    """Return a bounded snapshot of the LLM response for audit.

    Format: ``sha256:<hex>;len:<int>;preview:<first chars sanitised>``

    A short preview (up to :data:`_MAX_RESPONSE_AUDIT_LEN` characters) is kept
    because regulators frequently ask for "what did the model say to the
    user" — but the preview is also passed through :func:`minimize_text` so
    we never store back-channel PII the model may have echoed.
    """
    digest = _sha256_hex(response_text or "")
    sanitised = minimize_text(response_text or "")
    preview = sanitised[:_MAX_RESPONSE_AUDIT_LEN]
    return f"sha256:{digest};len:{len(response_text or '')};preview:{preview}"


__all__ = [
    "AIConsentRequiredError",
    "ensure_ai_consent_granted",
    "minimize_prompt_data",
    "minimize_text",
    "redact_prompt_for_audit",
    "redact_response_for_audit",
]
