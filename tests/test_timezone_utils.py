"""Tests for user timezone resolution in financial period contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from app.utils.timezone_utils import local_today, resolve_user_timezone


def test_resolve_user_timezone_accepts_valid_iana_name() -> None:
    resolution = resolve_user_timezone("Pacific/Kiritimati")

    assert resolution.name == "Pacific/Kiritimati"
    assert resolution.fallback_used is False
    assert resolution.requested == "Pacific/Kiritimati"


def test_resolve_user_timezone_falls_back_for_invalid_name() -> None:
    resolution = resolve_user_timezone("Mars/Olympus_Mons")

    assert resolution.name == "America/Sao_Paulo"
    assert resolution.fallback_used is True
    assert resolution.requested == "Mars/Olympus_Mons"


def test_local_today_uses_resolved_timezone_calendar_day() -> None:
    resolution = resolve_user_timezone("America/Sao_Paulo")

    local_day = local_today(
        resolution,
        now_utc=datetime(2026, 5, 22, 2, 30, tzinfo=UTC),
    )

    assert local_day.isoformat() == "2026-05-21"
