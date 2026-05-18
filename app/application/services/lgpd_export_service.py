"""LGPD data export service — single-call user data portability (#1256).

Uses the LGPD registry as the source of truth for which entities are
included. Each entity is queried with a user-scoped filter and serialised
generically from its SQLAlchemy column metadata so the export pipeline
never silently drops a new model added to the registry.

Output shape::

    {
        "metadata": {
            "generated_at": "<ISO8601 UTC>",
            "user_id": "<uuid>",
            "registry_version": "1.0",  # bump when entity coverage changes
            "scope": "lgpd_full_export",
        },
        "users": [{...}],            # User row (single-element list for shape parity)
        "consents": [{...}],         # versioned consent events
        "transactions": [{...}],
        "goals": [{...}],
        ...
        "retentions": [              # entries flagged as RETAIN
            {
                "entity": "fiscal_documents",
                "reason": "fiscal",
                "retention_days": 1825,
                "explanation": "Brazilian tax law requires 5y retention",
            },
        ],
    }

Boundary rules:

- No HTTP coupling (no Flask request/response).
- Returns ``dict``; the controller serialises to JSON.
- All queries are user-scoped via ``user_id``. The User entity is keyed
  by its primary-key ``id`` column.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from flask import current_app
from sqlalchemy import inspect as sa_inspect

from app.lgpd import REGISTRY, DeletionStrategy, EntityRule

_REGISTRY_VERSION = "1.0"
_SCOPE = "lgpd_full_export"


def _iso(dt: datetime | None) -> str | None:
    """Render a datetime as an ISO-8601 string in UTC.

    Naive datetimes are treated as UTC. Aware datetimes are preserved.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).isoformat()
    return dt.isoformat()


def _serialize_value(value: Any) -> Any:
    """Convert a single column value to a JSON-friendly primitive."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        # Never ship raw bytes in an export. Convert to hex for legibility.
        return value.hex()
    if hasattr(value, "isoformat"):
        # datetime.date / datetime.time fall through here.
        return value.isoformat()
    return value


# Columns that must NEVER appear in the LGPD export — even though they belong
# to the user, exporting them creates a credentials/auth-secret leak vector
# without any LGPD upside. Compared per (table_name, column_name) so we can
# scope an exclusion precisely without affecting unrelated tables.
_SENSITIVE_COLUMNS: frozenset[tuple[str, str]] = frozenset(
    {
        ("users", "password"),
        ("users", "current_jti"),
        ("users", "refresh_token_jti"),
        ("users", "password_reset_token_hash"),
        ("users", "password_reset_token_expires_at"),
        ("users", "password_reset_requested_at"),
        ("users", "email_verification_token_hash"),
        ("users", "email_verification_token_expires_at"),
    }
)


def _serialize_row(row: Any) -> dict[str, Any]:
    """Serialise a SQLAlchemy row to a plain dict using its mapper metadata.

    Sensitive credential / session-token columns listed in
    :data:`_SENSITIVE_COLUMNS` are filtered out — exposing them would leak
    auth secrets to no LGPD purpose.

    Iterates via ``mapper.column_attrs`` (not ``__table__.columns``) so
    Python attribute names and DB column names can diverge. Concrete trap:
    ``Simulation`` declares ``extra_metadata = db.Column("metadata", db.JSON, …)``
    — the Column's ``.name`` AND ``.key`` are both ``"metadata"``, but the
    actual Python attribute is ``extra_metadata``. Using ``column_attrs``
    surfaces the correct attribute name via ``attr.key``; the DB name lives
    in ``attr.expression.name``. Reading the value via
    ``getattr(row, "metadata")`` would otherwise resolve to SQLAlchemy's
    reserved ``Base.metadata`` instance and crash Flask's JSON encoder
    with ``TypeError: Object of type MetaData is not JSON serializable``.
    """
    table_name = row.__table__.name
    mapper = sa_inspect(row.__class__)
    out: dict[str, Any] = {}
    for col_attr in mapper.column_attrs:
        col_name = col_attr.expression.name
        if (table_name, col_name) in _SENSITIVE_COLUMNS:
            continue
        py_attr = col_attr.key
        out[col_name] = _serialize_value(getattr(row, py_attr))
    return out


def _query_rows_for_entity(rule: EntityRule, user_id: UUID) -> list[Any]:
    """Run the user-scoped query for one registry entry.

    The ``User`` entity is special-cased: its ``user_id_field`` is ``"id"``
    (primary key) and we return at most one row.
    """
    # ``rule.model`` is a SQLAlchemy model class; ``.query`` is injected by
    # Flask-SQLAlchemy at runtime and is therefore opaque to mypy.
    query_ns: Any = rule.model.query  # type: ignore[attr-defined]
    if rule.user_id_field == "id":
        row = query_ns.filter_by(id=user_id).first()
        return [row] if row is not None else []
    column = getattr(rule.model, rule.user_id_field)
    rows: list[Any] = query_ns.filter(column == user_id).all()
    return rows


def _build_retentions_section() -> list[dict[str, Any]]:
    """List entities retained beyond user lifetime with reason and window."""
    return [
        {
            "entity": rule.table_name,
            "reason": rule.retention_reason.value,
            "retention_days": rule.retention_days,
            "explanation": rule.description,
        }
        for rule in REGISTRY
        if rule.deletion_strategy == DeletionStrategy.RETAIN
    ]


def _build_metadata(user_id: UUID) -> dict[str, Any]:
    """Return the static metadata section of the export package."""
    return {
        "generated_at": _iso(datetime.now(UTC)),
        "user_id": str(user_id),
        "registry_version": _REGISTRY_VERSION,
        "scope": _SCOPE,
    }


def _export_one_entity(
    rule: EntityRule, user_id: UUID, failed: list[str]
) -> list[dict[str, Any]]:
    """Serialise one registry entity, recording the failure instead of
    raising so the export never 500s on a single bad query.

    SQLite-passing tests can miss Postgres-only edge cases (enum case
    folding, JSON column quirks, etc.). Treating each entity as
    independently fallible keeps the export robust to those drifts —
    callers see the partial pack plus a ``warnings.failed_entities`` list.
    """
    try:
        rows = _query_rows_for_entity(rule, user_id)
        return [_serialize_row(row) for row in rows]
    except Exception as exc:  # noqa: BLE001  # defensive boundary, see docstring
        current_app.logger.exception(
            "event=lgpd.export.entity_failed user_id=%s entity=%s error=%s",
            user_id,
            rule.table_name,
            type(exc).__name__,
        )
        failed.append(rule.table_name)
        return []


def build_user_export(user_id: UUID) -> dict[str, Any]:
    """Generate the full LGPD export package for ``user_id``.

    The caller must enforce authentication before invoking this function.
    Entities flagged ``export_included=False`` in the registry are
    intentionally omitted (e.g. refresh tokens, LLM audit logs).

    Each entity is queried independently; a failure on one (e.g. a
    Postgres-only column quirk a SQLite test missed) is logged and the
    entity reports an empty list rather than crashing the whole export.
    """
    failed: list[str] = []
    package: dict[str, Any] = {"metadata": _build_metadata(user_id)}
    for rule in REGISTRY:
        if not rule.export_included:
            continue
        package[rule.table_name] = _export_one_entity(rule, user_id, failed)
    package["retentions"] = _build_retentions_section()
    if failed:
        package["warnings"] = {"failed_entities": failed}
    return package


__all__ = ["build_user_export"]
