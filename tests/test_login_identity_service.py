from __future__ import annotations

import pytest

from app.application.services.login_identity_service import resolve_login_identity
from app.models.user import User


def test_resolve_login_identity_normalizes_email() -> None:
    email_user = User(name="Email User", email="email@test.com", password="hash")

    resolved = resolve_login_identity(
        email="  EMAIL@Test.com  ",
        find_user_by_email=lambda value: (
            email_user if value == email_user.email else None
        ),
    )

    assert resolved.principal == "email@test.com"
    assert resolved.user is email_user


def test_resolve_login_identity_requires_email() -> None:
    with pytest.raises(ValueError, match="Email is required."):
        resolve_login_identity(
            email="   ",
            find_user_by_email=lambda _value: None,
        )
