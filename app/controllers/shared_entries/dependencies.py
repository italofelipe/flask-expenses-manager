from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from flask import Flask, current_app

from app.models.shared_entry import Invitation, SharedEntry
from app.services.invitation_service import (
    accept_invitation,
    create_invitation,
    list_invitations,
    revoke_invitation,
)
from app.services.shared_entry_service import (
    list_shared_by_me,
    list_shared_with_me,
    revoke_share,
    share_entry,
    update_shared_entry,
)

SHARED_ENTRIES_DEPENDENCIES_EXTENSION_KEY = "shared_entries_dependencies"


@dataclass(frozen=True)
class SharedEntriesDependencies:
    share_entry: Callable[[UUID, UUID, str], SharedEntry]
    list_shared_by_me: Callable[[UUID], list[SharedEntry]]
    list_shared_with_me: Callable[[UUID], list[SharedEntry]]
    revoke_share: Callable[[UUID, UUID], SharedEntry]
    update_shared_entry: Callable[..., SharedEntry]
    list_invitations: Callable[[UUID], list[Invitation]]
    create_invitation: Callable[
        [UUID, UUID, str, float | None, float | None, str | None, int],
        Invitation,
    ]
    accept_invitation: Callable[[str, UUID], Invitation]
    revoke_invitation: Callable[[UUID, UUID], Invitation]


def _default_dependencies() -> SharedEntriesDependencies:
    return SharedEntriesDependencies(
        share_entry=share_entry,
        list_shared_by_me=list_shared_by_me,
        list_shared_with_me=list_shared_with_me,
        revoke_share=revoke_share,
        update_shared_entry=update_shared_entry,
        list_invitations=list_invitations,
        create_invitation=create_invitation,
        accept_invitation=accept_invitation,
        revoke_invitation=revoke_invitation,
    )


def register_shared_entries_dependencies(
    app: Flask,
    dependencies: SharedEntriesDependencies | None = None,
) -> None:
    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(SHARED_ENTRIES_DEPENDENCIES_EXTENSION_KEY, dependencies)


def get_shared_entries_dependencies() -> SharedEntriesDependencies:
    configured = current_app.extensions.get(SHARED_ENTRIES_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, SharedEntriesDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[SHARED_ENTRIES_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback
