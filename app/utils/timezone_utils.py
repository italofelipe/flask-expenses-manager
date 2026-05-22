"""User timezone helpers for financial period resolution.

The API stores canonical timestamps independently from user locale, but period
selection for financial insights must follow the user's local calendar day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_USER_TIMEZONE = "America/Sao_Paulo"
USER_TIMEZONE_HEADER = "X-Auraxis-Timezone"


@dataclass(frozen=True)
class UserTimezoneResolution:
    """Validated timezone selected for a request."""

    name: str
    zone: ZoneInfo
    fallback_used: bool
    requested: str | None


def utc_now() -> datetime:
    """Return the current UTC datetime; kept injectable for deterministic tests."""
    return datetime.now(UTC)


def resolve_user_timezone(raw_timezone: object) -> UserTimezoneResolution:
    """Resolve an IANA timezone name, falling back safely when absent/invalid."""
    requested = str(raw_timezone or "").strip() or None
    if requested is not None:
        try:
            return UserTimezoneResolution(
                name=requested,
                zone=ZoneInfo(requested),
                fallback_used=False,
                requested=requested,
            )
        except (ZoneInfoNotFoundError, ValueError):
            pass

    return UserTimezoneResolution(
        name=DEFAULT_USER_TIMEZONE,
        zone=ZoneInfo(DEFAULT_USER_TIMEZONE),
        fallback_used=True,
        requested=requested,
    )


def local_today(
    resolution: UserTimezoneResolution,
    *,
    now_utc: datetime | None = None,
) -> date:
    """Return today's date in the resolved user timezone."""
    now = now_utc or utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(resolution.zone).date()


__all__ = [
    "DEFAULT_USER_TIMEZONE",
    "USER_TIMEZONE_HEADER",
    "UserTimezoneResolution",
    "local_today",
    "resolve_user_timezone",
    "utc_now",
]
