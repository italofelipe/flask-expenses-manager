from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast
from uuid import UUID

from flask import Flask, current_app

from app.models.user import User
from app.models.wallet import Wallet

USER_DEPENDENCIES_EXTENSION_KEY = "user_dependencies"


@dataclass(frozen=True)
class UserDependencies:
    get_user_by_id: Callable[[UUID], User | None]
    list_wallet_entries_by_user_id: Callable[[UUID], list[Wallet]]


def _get_user_by_id(user_id: UUID) -> User | None:
    return cast(User | None, User.query.filter_by(id=user_id).first())


def _list_wallet_entries_by_user_id(user_id: UUID) -> list[Wallet]:
    return cast(list[Wallet], Wallet.query.filter_by(user_id=user_id).all())


def _default_dependencies() -> UserDependencies:
    return UserDependencies(
        get_user_by_id=_get_user_by_id,
        list_wallet_entries_by_user_id=_list_wallet_entries_by_user_id,
    )


def register_user_dependencies(
    app: Flask,
    dependencies: UserDependencies | None = None,
) -> None:
    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(USER_DEPENDENCIES_EXTENSION_KEY, dependencies)


def get_user_dependencies() -> UserDependencies:
    configured = current_app.extensions.get(USER_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, UserDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[USER_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback
