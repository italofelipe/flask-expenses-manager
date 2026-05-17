"""LGPD module — data subject rights enforcement.

This package is the technical source of truth for personal-data coverage in the
backend. Every SQLAlchemy model that stores user-linked data is registered in
``registry.py`` with rules for export, deletion, anonymisation and retention.

The registry powers:

- ``GET /user/me/export`` (issue #1256) — what to ship in the export bundle
- ``DELETE /user/me`` (issue #1257) — how to handle each row on erasure
- AI/LLM minimisation tracking (issue #1258) — which entries are LLM-related
- CI guard (``tests/lgpd/test_registry.py``) — fails when a new model with a
  user-linking column is added without being registered

See ``docs/lgpd/REGISTRY.md`` for the developer guide.
"""

from __future__ import annotations

from app.lgpd.registry import (
    REGISTRY,
    DeletionStrategy,
    EntityRule,
    RetentionReason,
    find_unregistered_models,
    get_registered_models,
)

__all__ = [
    "REGISTRY",
    "DeletionStrategy",
    "EntityRule",
    "RetentionReason",
    "find_unregistered_models",
    "get_registered_models",
]
