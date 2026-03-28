from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models.user import User

UserFinder = Callable[[str], User | None]


@dataclass(frozen=True)
class ResolvedLoginIdentity:
    principal: str
    user: User | None


def resolve_login_identity(
    *,
    email: str,
    find_user_by_email: UserFinder,
) -> ResolvedLoginIdentity:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("Email is required.")
    return ResolvedLoginIdentity(
        principal=normalized_email,
        user=find_user_by_email(normalized_email),
    )


__all__ = ["ResolvedLoginIdentity", "resolve_login_identity"]
