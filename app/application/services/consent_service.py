"""Consent application service — LGPD versioned consent log (#1259).

Append-only audit log of consent grants and revocations. The service is
intentionally thin: it owns idempotency, ordering and the contract used
by both the REST controller and the LGPD export/delete pipelines.

Boundary rules:

- No HTTP coupling here (no ``request``, no ``jsonify``).
- All writes commit before returning.
- ``record_consent`` is idempotent on ``(user, kind, version, action)``:
  identical events are coalesced to the first row so a retry from a
  flaky client never duplicates the log.
"""

from __future__ import annotations

from uuid import UUID

from app.extensions.database import db
from app.models.consent import (
    Consent,
    ConsentAction,
    ConsentKind,
    ConsentSource,
)


def record_consent(
    *,
    user_id: UUID,
    kind: ConsentKind,
    version: str,
    action: ConsentAction,
    source: ConsentSource,
) -> Consent:
    """Persist a consent event, returning the row.

    Idempotent on ``(user_id, kind, version, action)``: if an identical
    event already exists (same user, kind, version and direction) the
    pre-existing row is returned unchanged. ``source`` is not part of
    the idempotency key — replaying the same accept event from a
    different channel still resolves to the original log entry.
    """
    existing: Consent | None = (
        Consent.query.filter_by(
            user_id=user_id,
            kind=kind,
            version=version,
            action=action,
        )
        .order_by(Consent.created_at.asc())
        .first()
    )
    if existing is not None:
        return existing

    event = Consent(
        user_id=user_id,
        kind=kind,
        version=version,
        action=action,
        source=source,
    )
    db.session.add(event)
    db.session.commit()
    return event


def list_consents_for_user(user_id: UUID) -> list[Consent]:
    """Return the latest event per ``ConsentKind`` for the user.

    Only kinds the user has ever interacted with appear in the list —
    a brand-new account returns an empty list. The result is ordered
    by ``ConsentKind`` enum value for stable serialisation.
    """
    rows: list[Consent] = (
        Consent.query.filter_by(user_id=user_id)
        .order_by(Consent.created_at.desc())
        .all()
    )
    latest_by_kind: dict[ConsentKind, Consent] = {}
    for row in rows:
        if row.kind not in latest_by_kind:
            latest_by_kind[row.kind] = row
    return [latest_by_kind[k] for k in ConsentKind if k in latest_by_kind]


def current_state_for(
    user_id: UUID,
    kind: ConsentKind,
) -> ConsentAction | None:
    """Return the latest action for ``(user, kind)`` or ``None`` if never set.

    Version-agnostic helper for auth gates that only need to know whether
    a user has the consent in any version (e.g. blocking AI features when
    the AI consent has been revoked).
    """
    latest: Consent | None = (
        Consent.query.filter_by(user_id=user_id, kind=kind)
        .order_by(Consent.created_at.desc())
        .first()
    )
    return latest.action if latest is not None else None
