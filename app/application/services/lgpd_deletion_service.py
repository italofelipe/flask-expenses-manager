"""LGPD account deletion service — registry-driven, auditable (#1257).

Replaces the legacy in-controller anonymisation with a single source-of-
truth iteration over the LGPD registry. Each entity is handled according
to its :class:`~app.lgpd.DeletionStrategy`:

- ``DELETE`` → hard ``DELETE FROM ... WHERE user_id = :id``
- ``ANONYMIZE`` → entity-specific PII reset (User has a full anonymisation
  recipe; AuditEvent nulls ``user_id``; SharingAuditEvent rewrites
  ``user_id`` to a sentinel because the column is ``NOT NULL``;
  Subscription nulls provider PII; Consent keeps the row pointing at the
  now-anonymised user)
- ``RETAIN`` → leave rows intact (fiscal documents — Brazilian tax law
  obligation; tallied in the report)

The service returns an audit report consumed by the controller; the
controller is responsible for persisting an :class:`AuditEvent` of type
``lgpd.account_deletion_started`` *before* calling this function, and an
``lgpd.account_deletion_completed`` event *after* the transaction
commits, so the LGPD trail survives even if the deletion itself nulls
the actor reference.

Boundary rules (per ``app/application/services/CLAUDE.md``):

- No HTTP coupling (the function never inspects ``request``).
- Single transaction — ``db.session.commit()`` happens once, at the end,
  so a failure mid-flight rolls everything back.
- Domain errors raise ``AppError``; the controller maps them to HTTP.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from werkzeug.security import generate_password_hash

from app.extensions.database import db
from app.lgpd import REGISTRY, DeletionStrategy, EntityRule
from app.models.user import User

# Sentinel UUID used in tables where ``user_id`` is ``NOT NULL`` and so
# cannot be anonymised by nulling. The sharing-audit table is the only
# current case. Picking the all-zero UUID makes the anonymisation visible
# at a glance in production data and is impossible to collide with a real
# user.
_ANONYMIZED_USER_SENTINEL: UUID = UUID(int=0)


# Anonymisation recipes for ``ANONYMIZE`` entities. The key is the
# ``table_name``; the value is a dict ``{column_name: value_or_callable}``.
# Callables receive the row and return the final value (used for ``users``
# where the anonymised email embeds the row id). Tables whose
# anonymisation strategy is "keep the row pointing to the anonymised
# user" (e.g. ``consents``) are intentionally absent — falling through
# to :func:`_apply_default_anonymise` is a no-op for them, which is what
# the LGPD policy requires.
_ANONYMIZE_RECIPES: dict[str, dict[str, Any]] = {
    "users": {
        "name": "Deleted User",
        "email": lambda row: f"deleted_{row.id}@deleted.auraxis",
        "birth_date": None,
        "state_uf": None,
        "occupation": None,
        "gender": None,
        "financial_objectives": None,
        "monthly_income_net": 0,
        "monthly_expenses": 0,
        "net_worth": 0,
        "initial_investment": 0,
        "monthly_investment": 0,
        "investment_goal_date": None,
        "avatar_url": None,
        "investor_profile": None,
        "investor_profile_suggested": None,
        "profile_quiz_score": None,
        "current_jti": None,
        "refresh_token_jti": None,
        "password_reset_token_hash": None,
        "password_reset_token_expires_at": None,
        "password_reset_requested_at": None,
        "email_verification_token_hash": None,
        "email_verification_token_expires_at": None,
    },
    "audit_events": {"user_id": None},
    "sharing_audit_events": {"user_id": _ANONYMIZED_USER_SENTINEL},
    "subscriptions": {
        # Keep the billing record for fiscal retention but null provider
        # PII (the only PII left after the FKs and amounts).
        "provider_subscription_id": None,
        "provider_customer_id": None,
        "provider_event_id": None,
    },
    # ``consents`` is intentionally omitted: LGPD process evidence is the
    # rule (#1259) and the row's user_id stays valid because the User row
    # is also ANONYMIZE rather than DELETE.
}


def _user_id_column(rule: EntityRule) -> Any:
    """Return the SQLAlchemy column used to scope a query to a user."""
    return getattr(rule.model, rule.user_id_field)


def _scoped_filter(rule: EntityRule, user_id: UUID) -> Any:
    """Build a per-entity filter that handles UUID-vs-string column types.

    ``AuditEvent.user_id`` is a ``String(64)`` column that stores the
    UUID's textual representation, while most other tables type their
    user link as ``UUID``. Comparing a Python ``UUID`` against a string
    column in SQLite returns the empty set silently, which would let
    rows escape anonymisation. Doing the filter with both forms is
    portable and matches the export service's expectation that the
    registry is the only source of coupling.
    """
    column = _user_id_column(rule)
    column_type = getattr(getattr(column, "type", None), "python_type", None)
    if column_type is str:
        return column == str(user_id)
    return column == user_id


def _hard_delete_entity(rule: EntityRule, user_id: UUID) -> int:
    """Hard-delete every row owned by ``user_id``. Returns the row count."""
    query = rule.model.query.filter(_scoped_filter(rule, user_id))  # type: ignore[attr-defined]
    count: int = int(query.count())
    if count:
        query.delete(synchronize_session=False)
    return count


def _resolve_recipe_value(value: Any, row: Any) -> Any:
    """Resolve a recipe entry — callables get the row, scalars pass through."""
    return value(row) if callable(value) else value


def _rows_to_anonymise(rule: EntityRule, user_id: UUID) -> list[Any]:
    """Return the rows the anonymise pass needs to touch."""
    if rule.user_id_field == "id":
        row = rule.model.query.filter_by(id=user_id).first()  # type: ignore[attr-defined]
        return [row] if row is not None else []
    return rule.model.query.filter(_scoped_filter(rule, user_id)).all()  # type: ignore[attr-defined,no-any-return]


def _anonymise_rows(rows: list[Any], recipe: dict[str, Any]) -> None:
    """Apply the recipe to each row in place."""
    for row in rows:
        for field, value in recipe.items():
            setattr(row, field, _resolve_recipe_value(value, row))


def _anonymize_entity(rule: EntityRule, user_id: UUID) -> int:
    """Apply the registered anonymisation recipe; returns rows touched."""
    rows = _rows_to_anonymise(rule, user_id)
    if not rows:
        return 0
    recipe = _ANONYMIZE_RECIPES.get(rule.table_name, {})
    if recipe:
        _anonymise_rows(rows, recipe)
    return len(rows)


def _count_retained(rule: EntityRule, user_id: UUID) -> int:
    """Count rows that will be retained for this entity."""
    column = getattr(rule.model, rule.user_id_field, None)
    if column is None:
        return 0
    return rule.model.query.filter(_scoped_filter(rule, user_id)).count()  # type: ignore[attr-defined,no-any-return]


def _retention_meta(rule: EntityRule) -> dict[str, Any]:
    """Build the ``retentions[]`` entry for one rule."""
    return {
        "entity": rule.table_name,
        "reason": rule.retention_reason.value,
        "retention_days": rule.retention_days,
        "explanation": rule.description,
    }


def _pass_delete(
    user_id: UUID,
) -> dict[str, int]:
    """First pass — hard-delete every DELETE-strategy entity."""
    counts: dict[str, int] = {}
    for rule in REGISTRY:
        if rule.deletion_strategy is not DeletionStrategy.DELETE:
            continue
        n = _hard_delete_entity(rule, user_id)
        if n:
            counts[rule.table_name] = n
    return counts


def _pass_anonymize(
    user_id: UUID,
) -> dict[str, int]:
    """Second pass — anonymise every ANONYMIZE-strategy entity."""
    counts: dict[str, int] = {}
    for rule in REGISTRY:
        if rule.deletion_strategy is not DeletionStrategy.ANONYMIZE:
            continue
        n = _anonymize_entity(rule, user_id)
        if n:
            counts[rule.table_name] = n
    return counts


def _pass_retain(
    user_id: UUID,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Third pass — count rows retained by legal obligation.

    Returns ``(counts, retentions_meta)`` so the report enumerates *both*
    the per-table counts and the human-readable legal-basis metadata.
    """
    counts: dict[str, int] = {}
    meta: list[dict[str, Any]] = []
    for rule in REGISTRY:
        if rule.deletion_strategy is not DeletionStrategy.RETAIN:
            continue
        n = _count_retained(rule, user_id)
        if n:
            counts[rule.table_name] = n
        meta.append(_retention_meta(rule))
    return counts, meta


def _finalise_user_row(user_id: UUID, now: datetime) -> None:
    """Apply the User-specific tail-end mutations.

    The ``ANONYMIZE`` recipe sets the public PII; this helper applies the
    two transformations that cannot live in the static recipe table:

    1. A real (but unusable) bcrypt-style hash overwrites ``password`` —
       the row stays cryptographically consistent but no one can log in.
    2. ``deleted_at`` is set so the auth gates at login / token check
       reject the row.
    """
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        return
    user.password = generate_password_hash(secrets.token_urlsafe(32))
    user.deleted_at = now


def _format_now() -> datetime:
    """Return the canonical 'now' for the deletion record."""
    return datetime.now(UTC).replace(tzinfo=None)


def delete_user_account(user_id: UUID) -> dict[str, Any]:
    """Delete the user account, applying registry strategies.

    The caller (controller) must enforce authentication AND password
    confirmation *before* invoking this function. This service only owns
    the data-side transformations; it does not check who the requester
    is.

    The function is transactional: every DELETE / UPDATE issued is part
    of a single ``db.session.commit()`` at the end. A SQLAlchemy
    exception aborts the transaction and bubbles up to the caller.

    Returns the audit report dict — see module docstring for shape.
    """
    now = _format_now()

    deleted_counts = _pass_delete(user_id)
    anonymised_counts = _pass_anonymize(user_id)
    retained_counts, retentions_meta = _pass_retain(user_id)

    _finalise_user_row(user_id, now)

    db.session.commit()

    return {
        "user_id": str(user_id),
        "deleted_at": now.isoformat(),
        "summary": {
            "deleted": deleted_counts,
            "anonymized": anonymised_counts,
            "retained": retained_counts,
        },
        "retentions": retentions_meta,
    }


__all__ = ["delete_user_account"]
