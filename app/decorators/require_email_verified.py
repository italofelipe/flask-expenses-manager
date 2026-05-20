"""Decorator that soft-blocks endpoints when the user has not confirmed their email
within the grace period.

Behavior:
- If `EMAIL_VERIFICATION_ENFORCE=false` (config flag), the decorator is a no-op.
- If the user has confirmed (User.email_verified_at is not None), proceeds.
- If the user is within the grace period (created_at + grace_days), proceeds.
- If the grace period has expired, returns HTTP 403 with code
  `EMAIL_VERIFICATION_REQUIRED` and metadata for the frontend to open the
  resend modal.

Reads continue working — apply this decorator only on mutation endpoints
(POST/PUT/PATCH/DELETE) so users can still see their data.

References:
- app/models/user.py — User.email_verification_required_now hybrid property
- config/__init__.py — EMAIL_VERIFICATION_GRACE_PERIOD_DAYS, EMAIL_VERIFICATION_ENFORCE
- .context/adr/email_verification_grace_period.md (TODO) — design rationale
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import current_app, jsonify

from app.auth.identity import (
    AuthContextError,
    RevokedTokenError,
    get_active_user,
)


def require_email_verified(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """Block endpoint with 403 when user is past grace period without email confirm."""

    @wraps(view_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not current_app.config.get("EMAIL_VERIFICATION_ENFORCE", True):
            return view_func(*args, **kwargs)

        try:
            resolved = get_active_user(optional=True)
        except (AuthContextError, RevokedTokenError):
            # auth_guard handles unauthenticated requests upstream; if we got here
            # without a valid context, let the underlying handler decide.
            return view_func(*args, **kwargs)

        if resolved is None:
            return view_func(*args, **kwargs)

        _, user = resolved
        if not user.email_verification_required_now:
            return view_func(*args, **kwargs)

        deadline = user.email_verification_deadline_at
        payload = {
            "error": "EMAIL_VERIFICATION_REQUIRED",
            "message": (
                "Confirme seu email para continuar usando o Auraxis. "
                "Sua conta passou de 14 dias sem confirmação e entrou em modo "
                "somente-leitura. Solicite um novo link de confirmação."
            ),
            "deadline_passed_at": deadline.isoformat()
            if deadline is not None
            else None,
            "resend_endpoint": "/auth/email/resend",
        }
        return jsonify(payload), 403

    return wrapper


__all__ = ["require_email_verified"]
