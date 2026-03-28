from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from app.models.user import User

LoginIdentifierKind = Literal["email", "name"]
UserFinder = Callable[[str], User | None]


@dataclass(frozen=True)
class ResolvedLoginIdentity:
    principal: str
    identifier_kind: LoginIdentifierKind
    user: User | None

    @property
    def uses_legacy_name_identifier(self) -> bool:
        return self.identifier_kind == "name"


def resolve_login_identity(
    *,
    email: str | None,
    name: str | None,
    find_user_by_email: UserFinder,
    find_user_by_name: UserFinder,
) -> ResolvedLoginIdentity:
    normalized_email = (email or "").strip()
    if normalized_email:
        return ResolvedLoginIdentity(
            principal=normalized_email,
            identifier_kind="email",
            user=find_user_by_email(normalized_email),
        )

    normalized_name = (name or "").strip()
    return ResolvedLoginIdentity(
        principal=normalized_name,
        identifier_kind="name",
        user=find_user_by_name(normalized_name),
    )


__all__ = ["ResolvedLoginIdentity", "resolve_login_identity"]
