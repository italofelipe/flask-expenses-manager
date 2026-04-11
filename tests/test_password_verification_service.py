"""Tests for password verification service — SEC-GAP-06."""

from __future__ import annotations

from typing import Any

from werkzeug.security import generate_password_hash

from app.application.services.password_verification_service import (
    hash_password,
    needs_rehash,
    verify_password_with_timing_protection,
)

# ---------------------------------------------------------------------------
# hash_password
# ---------------------------------------------------------------------------


def test_hash_password_produces_argon2id_hash() -> None:
    result = hash_password("StrongPass@123")
    assert result.startswith("$argon2id$")


def test_hash_password_different_each_call() -> None:
    h1 = hash_password("SamePassword@1")
    h2 = hash_password("SamePassword@1")
    assert h1 != h2  # different salts


# ---------------------------------------------------------------------------
# needs_rehash
# ---------------------------------------------------------------------------


def test_needs_rehash_returns_false_for_argon2id() -> None:
    argon2_hash = hash_password("password123")
    assert needs_rehash(argon2_hash) is False


def test_needs_rehash_returns_true_for_werkzeug_pbkdf2() -> None:
    legacy_hash = generate_password_hash("password123")
    assert needs_rehash(legacy_hash) is True


# ---------------------------------------------------------------------------
# verify_password_with_timing_protection — happy paths
# ---------------------------------------------------------------------------


def test_verify_argon2id_hash_correct_password() -> None:
    pw = "StrongPass@123"
    h = hash_password(pw)
    assert (
        verify_password_with_timing_protection(password_hash=h, plain_password=pw)
        is True
    )


def test_verify_argon2id_hash_wrong_password() -> None:
    h = hash_password("correct-password")
    assert (
        verify_password_with_timing_protection(
            password_hash=h, plain_password="wrong-password"
        )
        is False
    )


def test_verify_werkzeug_pbkdf2_hash_correct_password() -> None:
    pw = "LegacyPass@456"
    legacy_hash = generate_password_hash(pw)
    assert (
        verify_password_with_timing_protection(
            password_hash=legacy_hash, plain_password=pw
        )
        is True
    )


def test_verify_werkzeug_pbkdf2_hash_wrong_password() -> None:
    legacy_hash = generate_password_hash("correct")
    assert (
        verify_password_with_timing_protection(
            password_hash=legacy_hash, plain_password="wrong"
        )
        is False
    )


# ---------------------------------------------------------------------------
# verify_password_with_timing_protection — user not found
# ---------------------------------------------------------------------------


def test_timing_protection_burns_cycles_when_no_hash(monkeypatch: Any) -> None:
    burned: list[str] = []
    monkeypatch.setattr(
        "app.application.services.password_verification_service._burn_hash_cycles",
        lambda pw: burned.append(pw),
    )
    result = verify_password_with_timing_protection(
        password_hash=None, plain_password="any"
    )
    assert result is False
    assert burned == ["any"]


# ---------------------------------------------------------------------------
# on_rehash callback
# ---------------------------------------------------------------------------


def test_rehash_callback_called_for_pbkdf2_on_success() -> None:
    pw = "MigrateMe@789"
    legacy_hash = generate_password_hash(pw)
    new_hashes: list[str] = []

    verify_password_with_timing_protection(
        password_hash=legacy_hash,
        plain_password=pw,
        on_rehash=new_hashes.append,
    )

    assert len(new_hashes) == 1
    assert new_hashes[0].startswith("$argon2id$")


def test_rehash_callback_not_called_for_pbkdf2_on_wrong_password() -> None:
    legacy_hash = generate_password_hash("correct")
    calls: list[str] = []

    verify_password_with_timing_protection(
        password_hash=legacy_hash,
        plain_password="wrong",
        on_rehash=calls.append,
    )

    assert calls == []


def test_rehash_callback_not_called_for_argon2id() -> None:
    pw = "AlreadyArgon@1"
    argon_hash = hash_password(pw)
    calls: list[str] = []

    verify_password_with_timing_protection(
        password_hash=argon_hash,
        plain_password=pw,
        on_rehash=calls.append,
    )

    assert calls == []
