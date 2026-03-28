from __future__ import annotations

from app.application.services.login_identity_service import resolve_login_identity
from app.models.user import User


def test_resolve_login_identity_prefers_email() -> None:
    email_user = User(name="Email User", email="email@test.com", password="hash")
    name_user = User(name="Legacy Name", email="name@test.com", password="hash")

    resolved = resolve_login_identity(
        email="email@test.com",
        name="Legacy Name",
        find_user_by_email=lambda value: (
            email_user if value == email_user.email else None
        ),
        find_user_by_name=lambda value: name_user if value == name_user.name else None,
    )

    assert resolved.identifier_kind == "email"
    assert resolved.principal == "email@test.com"
    assert resolved.user is email_user
    assert resolved.uses_legacy_name_identifier is False


def test_resolve_login_identity_falls_back_to_name() -> None:
    user = User(name="Legacy Name", email="legacy@test.com", password="hash")

    resolved = resolve_login_identity(
        email=None,
        name="Legacy Name",
        find_user_by_email=lambda _value: None,
        find_user_by_name=lambda value: user if value == user.name else None,
    )

    assert resolved.identifier_kind == "name"
    assert resolved.principal == "Legacy Name"
    assert resolved.user is user
    assert resolved.uses_legacy_name_identifier is True
