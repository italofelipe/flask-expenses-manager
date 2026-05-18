"""Evidence path validation for AI insight items (issue #1300).

LLMs may produce items whose ``dimension`` label disagrees with the actual
``evidence`` paths (e.g. a "budgets" item supported only by
``current_period.paid.expense_total``). This module enforces the domain
contract: each ``dimension`` requires at least one evidence path matching
the canonical prefixes of its snapshot section.

Decisions (chat 2026-05-18)
---------------------------
- Reject offending items silently, log a structured warning, keep the rest.
- When **every** item is rejected, the caller raises ``LLMProviderError``.
- Whitelist of canonical path prefixes per dimension below.
- ``general`` accepts any KNOWN prefix (so multi-surface narrative still works).

The module exports two callables: :func:`is_known_evidence_prefix` and
:func:`validate_item_evidence`. Callers integrate them in the LLM response
coercion pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


# Canonical snapshot path prefixes recognised by the validator. A path
# matches a prefix when it equals the prefix or begins with ``prefix + '.'``
# or ``prefix + '['``. The set below is intentionally additive — when the
# snapshot schema grows a new section, add the prefix here.
_KNOWN_SNAPSHOT_PREFIXES: frozenset[str] = frozenset(
    {
        "schema_version",
        "period_type",
        "currency",
        "timezone",
        "anchor_date",
        "period",
        "current_period",
        "comparisons",
        "daily_series",
        "extremes",
        "categories",
        "transactions",
        "budgets",
        "goals",
        "credit_cards",
        "wallet",
        "data_quality",
    }
)


# Map dimension → tuple of allowed prefixes. ``None`` means "any known prefix".
_DIMENSION_EVIDENCE_PREFIXES: dict[str, tuple[str, ...] | None] = {
    "general": None,
    "transactions": (
        "transactions",
        "daily_series",
        "extremes",
        "categories",
        "current_period.paid",
        "current_period.commitments",
        "comparisons",
    ),
    "credit_cards": ("credit_cards",),
    "goals": ("goals",),
    "budgets": ("budgets",),
}


def is_known_evidence_prefix(path: str) -> bool:
    """Return True when ``path`` begins with a canonical snapshot prefix."""
    if not isinstance(path, str) or not path.strip():
        return False
    candidate = path.strip()
    root = candidate.split(".", 1)[0].split("[", 1)[0]
    return root in _KNOWN_SNAPSHOT_PREFIXES


def _matches_prefix(path: str, prefix: str) -> bool:
    """A path matches a prefix when equal, or starts with ``prefix.`` / ``prefix[``."""
    candidate = path.strip()
    if candidate == prefix:
        return True
    return candidate.startswith(prefix + ".") or candidate.startswith(prefix + "[")


def validate_item_evidence(item: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate that ``item.evidence`` is consistent with ``item.dimension``.

    Returns ``(True, None)`` when valid; ``(False, reason)`` otherwise.
    Reasons are stable strings suitable for structured logs/metrics.

    Rules:
    - ``dimension`` must be a known key in ``_DIMENSION_EVIDENCE_PREFIXES``.
    - ``evidence`` must be a non-empty list of strings.
    - Every evidence path must begin with a known snapshot prefix
      (rejects fabricated paths like ``inventado.algo``).
    - For specific dimensions, at least one evidence path must match the
      dimension's allowed prefixes. ``general`` skips this check.
    """
    dimension = item.get("dimension")
    if not isinstance(dimension, str) or dimension not in _DIMENSION_EVIDENCE_PREFIXES:
        return False, "invalid_dimension"

    evidence = item.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return False, "missing_evidence"

    paths = [str(p).strip() for p in evidence if isinstance(p, str) and p.strip()]
    if not paths:
        return False, "empty_evidence"

    unknown = [p for p in paths if not is_known_evidence_prefix(p)]
    if unknown:
        return False, "unknown_path_prefix"

    allowed = _DIMENSION_EVIDENCE_PREFIXES[dimension]
    if allowed is None:
        return True, None

    has_match = any(_matches_prefix(p, prefix) for p in paths for prefix in allowed)
    if not has_match:
        return False, "dimension_evidence_mismatch"

    return True, None


def filter_valid_items(
    items: list[dict[str, Any]],
    *,
    user_id: Any = None,
) -> list[dict[str, Any]]:
    """Return only items whose evidence is valid for their declared dimension.

    Rejected items are logged at WARNING with reason + sanitized item fields
    (no PII). Empty result is the caller's responsibility to surface as an
    LLM error — this helper does not raise.
    """
    accepted: list[dict[str, Any]] = []
    for item in items:
        ok, reason = validate_item_evidence(item)
        if ok:
            accepted.append(item)
            continue
        log.warning(
            "ai_advisory.evidence_validation.rejected user=%s reason=%s "
            "dimension=%s type=%s evidence=%s",
            user_id,
            reason,
            item.get("dimension"),
            item.get("type"),
            item.get("evidence"),
        )
    return accepted


__all__ = [
    "filter_valid_items",
    "is_known_evidence_prefix",
    "validate_item_evidence",
]
