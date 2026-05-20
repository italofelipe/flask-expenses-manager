"""Decorators for endpoint-level enforcement."""

from app.decorators.require_email_verified import require_email_verified

__all__ = ["require_email_verified"]
