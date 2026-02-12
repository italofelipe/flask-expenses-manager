from __future__ import annotations

from typing import Any

from werkzeug.security import generate_password_hash

from app.application.services import password_verification_service
from app.application.services.password_verification_service import (
    verify_password_with_timing_protection,
)


def test_verify_password_with_timing_protection_matches_valid_hash() -> None:
    password = "StrongPass@123"
    password_hash = generate_password_hash(password)

    assert (
        verify_password_with_timing_protection(
            password_hash=password_hash,
            plain_password=password,
        )
        is True
    )


def test_verify_password_with_timing_protection_burns_hash_cycles_when_user_missing(
    monkeypatch: Any,
) -> None:
    burn_calls: list[str] = []
    hash_verify_calls: list[tuple[str, str]] = []

    def _fake_burn_hash_cycles(plain_password: str) -> None:
        burn_calls.append(plain_password)

    def _fake_check_password_hash(password_hash: str, plain_password: str) -> bool:
        hash_verify_calls.append((password_hash, plain_password))
        return False

    monkeypatch.setattr(
        password_verification_service,
        "_burn_hash_cycles",
        _fake_burn_hash_cycles,
    )

    monkeypatch.setattr(
        password_verification_service,
        "check_password_hash",
        _fake_check_password_hash,
    )

    result = verify_password_with_timing_protection(
        password_hash=None,
        plain_password="WrongPass@123",
    )

    assert result is False
    assert burn_calls == ["WrongPass@123"]
    assert hash_verify_calls == []
