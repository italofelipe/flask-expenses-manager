from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_naive() -> datetime:
    return utc_now().replace(tzinfo=None)


def iso_utc_now_naive() -> str:
    return utc_now_naive().isoformat()


def utc_now_compatible_with(value: datetime) -> datetime:
    """Return current UTC datetime with compatibility for naive/aware comparison."""
    now = utc_now()
    if value.tzinfo is None:
        return now.replace(tzinfo=None)
    return now.astimezone(value.tzinfo)
