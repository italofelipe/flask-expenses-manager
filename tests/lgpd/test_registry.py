"""Tests for the LGPD personal-data registry (issue #1255)."""

from __future__ import annotations

from app.lgpd import (
    REGISTRY,
    DeletionStrategy,
    EntityRule,
    RetentionReason,
    find_unregistered_models,
)


def test_registry_is_non_empty() -> None:
    """The registry must list at least one entity."""
    assert len(REGISTRY) > 0


def test_registry_entries_are_entity_rules() -> None:
    """Every registry entry is a frozen ``EntityRule`` dataclass."""
    for entry in REGISTRY:
        assert isinstance(entry, EntityRule)


def test_all_user_linked_models_are_registered() -> None:
    """CI gate — adding a new user-linked model without registering fails.

    Walks ``app.models`` and asserts that every SQLAlchemy model with a
    user-linking column (``user_id``, ``owner_id``, ``from_user_id``,
    ``to_user_id`` — or the ``User`` model itself) is present in the LGPD
    registry. See ``docs/lgpd/REGISTRY.md`` for how to add new models.
    """
    unregistered = find_unregistered_models()
    assert unregistered == [], (
        "Models with user-linking columns not in LGPD registry: "
        f"{unregistered}. Add them to app/lgpd/registry.py — see "
        "docs/lgpd/REGISTRY.md."
    )


def test_user_model_is_registered_with_id_field() -> None:
    """User is the base entity, registered with ``user_id_field='id'``."""
    user_entries = [r for r in REGISTRY if r.model.__name__ == "User"]
    assert len(user_entries) == 1
    assert user_entries[0].user_id_field == "id"
    assert user_entries[0].table_name == "users"


def test_no_duplicate_models_in_registry() -> None:
    """No model class appears twice in the registry."""
    models = [r.model for r in REGISTRY]
    assert len(models) == len(set(models)), "Duplicate model in REGISTRY"


def test_no_duplicate_table_names() -> None:
    """No table name appears twice in the registry."""
    names = [r.table_name for r in REGISTRY]
    assert len(names) == len(set(names)), "Duplicate table_name in REGISTRY"


def test_table_name_matches_model_tablename() -> None:
    """Each entry's ``table_name`` must match the model's ``__tablename__``."""
    for entry in REGISTRY:
        assert entry.table_name == entry.model.__tablename__, (
            f"{entry.model.__name__}: table_name mismatch "
            f"({entry.table_name!r} vs {entry.model.__tablename__!r})"
        )


def test_user_id_field_exists_on_model() -> None:
    """Each ``user_id_field`` must be a real column on the model."""
    for entry in REGISTRY:
        columns = {c.name for c in entry.model.__table__.columns}
        assert entry.user_id_field in columns, (
            f"{entry.table_name}: user_id_field={entry.user_id_field!r} "
            f"is not a column on {entry.model.__name__}"
        )


def test_retain_strategy_requires_retention_reason() -> None:
    """``RETAIN`` deletion requires a non-NONE retention reason."""
    for entry in REGISTRY:
        if entry.deletion_strategy == DeletionStrategy.RETAIN:
            assert entry.retention_reason != RetentionReason.NONE, (
                f"{entry.table_name}: RETAIN requires retention_reason != NONE"
            )


def test_retention_days_consistent_with_reason() -> None:
    """``retention_reason=NONE`` implies ``retention_days=None``."""
    for entry in REGISTRY:
        if entry.retention_reason == RetentionReason.NONE:
            assert entry.retention_days is None, (
                f"{entry.table_name}: NONE retention requires retention_days=None"
            )


def test_every_entry_has_description() -> None:
    """Each entry has a non-empty one-line description."""
    for entry in REGISTRY:
        assert entry.description.strip(), f"{entry.table_name} missing description"


def test_known_critical_models_present() -> None:
    """Spec ACs — critical LGPD-relevant entities are covered."""
    tables = {r.table_name for r in REGISTRY}
    required = {
        "users",
        "transactions",
        "llm_audit_logs",
        "ai_insight_runs",
        "ai_insights",
        "refresh_tokens",
        "push_subscriptions",
        "shared_entries",
        "fiscal_documents",
        "subscriptions",
    }
    missing = required - tables
    assert not missing, f"Critical LGPD entities missing: {missing}"


def test_entity_rule_is_frozen() -> None:
    """``EntityRule`` is immutable — defending invariants by construction."""
    entry = REGISTRY[0]
    try:
        entry.table_name = "tampered"  # type: ignore[misc]
    except Exception:  # noqa: BLE001 - expecting FrozenInstanceError
        return
    raise AssertionError("EntityRule must be frozen (immutable)")
