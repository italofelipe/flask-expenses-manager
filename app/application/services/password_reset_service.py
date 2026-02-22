from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from flask import current_app

from app.extensions.database import db
from app.models.user import User

PASSWORD_RESET_NEUTRAL_MESSAGE = (
    "If an account exists for this email, recovery instructions were sent."
)
PASSWORD_RESET_SUCCESS_MESSAGE = "Password reset completed successfully."
PASSWORD_RESET_INVALID_TOKEN_MESSAGE = "Invalid or expired password reset token."


@dataclass(frozen=True)
class PasswordResetResult:
    ok: bool
    message: str


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _secret_key() -> str:
    return str(current_app.config.get("SECRET_KEY", ""))


def _token_ttl_minutes() -> int:
    raw_value = current_app.config.get("PASSWORD_RESET_TOKEN_TTL_MINUTES", 30)
    try:
        ttl = int(raw_value)
    except (TypeError, ValueError):
        ttl = 30
    return max(1, ttl)


def _token_digest(token: str) -> str:
    digest = hmac.new(
        key=_secret_key().encode("utf-8"),
        msg=token.encode("utf-8"),
        digestmod=hashlib.sha256,
    )
    return digest.hexdigest()


def _testing_outbox() -> list[dict[str, str]]:
    outbox = current_app.extensions.setdefault("password_reset_outbox", [])
    if isinstance(outbox, list):
        return cast(list[dict[str, str]], outbox)
    current_app.extensions["password_reset_outbox"] = []
    return cast(list[dict[str, str]], current_app.extensions["password_reset_outbox"])


def _dispatch_reset_instructions(*, email: str, token: str) -> None:
    base_url = str(current_app.config.get("PASSWORD_RESET_FRONTEND_URL", "")).strip()
    if base_url:
        separator = "&" if "?" in base_url else "?"
        reset_url = f"{base_url}{separator}token={token}"
    else:
        reset_url = "n/a"

    if bool(current_app.config.get("TESTING")):
        _testing_outbox().append(
            {
                "email": email,
                "token": token,
                "reset_url": reset_url,
            }
        )

    current_app.logger.info(
        (
            "event=auth.password_reset_instructions_dispatched "
            "email=%s reset_url_present=%s"
        ),
        email,
        bool(base_url),
    )


def request_password_reset(email: str) -> PasswordResetResult:
    normalized_email = email.strip().lower()
    user = User.query.filter_by(email=normalized_email).first()
    if user is None:
        return PasswordResetResult(ok=True, message=PASSWORD_RESET_NEUTRAL_MESSAGE)

    token = secrets.token_urlsafe(48)
    user.password_reset_token_hash = _token_digest(token)
    user.password_reset_token_expires_at = _utcnow() + timedelta(
        minutes=_token_ttl_minutes()
    )
    user.password_reset_requested_at = _utcnow()
    db.session.commit()

    _dispatch_reset_instructions(email=normalized_email, token=token)
    current_app.logger.info(
        "event=auth.password_reset_requested user_id=%s",
        str(user.id),
    )
    return PasswordResetResult(ok=True, message=PASSWORD_RESET_NEUTRAL_MESSAGE)


def reset_password(*, token: str, new_password_hash: str) -> PasswordResetResult:
    digest = _token_digest(token)
    user = User.query.filter_by(password_reset_token_hash=digest).first()
    now = _utcnow()
    if user is None or user.password_reset_token_expires_at is None:
        return PasswordResetResult(
            ok=False,
            message=PASSWORD_RESET_INVALID_TOKEN_MESSAGE,
        )
    expires_at = user.password_reset_token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < now:
        return PasswordResetResult(
            ok=False,
            message=PASSWORD_RESET_INVALID_TOKEN_MESSAGE,
        )

    user.password = new_password_hash
    user.current_jti = None
    user.password_reset_token_hash = None
    user.password_reset_token_expires_at = None
    user.password_reset_requested_at = None
    db.session.commit()

    current_app.logger.info(
        "event=auth.password_reset_completed user_id=%s",
        str(user.id),
    )
    return PasswordResetResult(ok=True, message=PASSWORD_RESET_SUCCESS_MESSAGE)
