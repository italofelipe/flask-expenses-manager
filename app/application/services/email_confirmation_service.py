from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from app.extensions.database import db
from app.http.runtime import (
    runtime_config,
    runtime_debug_or_testing,
    runtime_extension,
    runtime_logger,
    set_runtime_extension,
)
from app.models.user import User
from app.services.email_provider import EmailMessage, get_default_email_provider

EMAIL_CONFIRMATION_NEUTRAL_MESSAGE = (
    "If an account exists for this email, confirmation instructions were sent."
)
EMAIL_CONFIRMATION_SUCCESS_MESSAGE = "Email confirmed successfully."
EMAIL_CONFIRMATION_INVALID_TOKEN_MESSAGE = (
    "Invalid or expired email confirmation token."
)


@dataclass(frozen=True)
class EmailConfirmationResult:
    ok: bool
    message: str


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _secret_key() -> str:
    return str(runtime_config("SECRET_KEY", ""))


def _token_ttl_minutes() -> int:
    raw_value = runtime_config("EMAIL_CONFIRMATION_TOKEN_TTL_MINUTES", 60 * 24)
    try:
        ttl = int(raw_value)
    except (TypeError, ValueError):
        ttl = 60 * 24
    return max(30, ttl)


def _token_digest(token: str) -> str:
    digest = hmac.new(
        key=_secret_key().encode("utf-8"),
        msg=token.encode("utf-8"),
        digestmod=hashlib.sha256,
    )
    return digest.hexdigest()


def _confirmation_outbox() -> list[dict[str, str]]:
    outbox = runtime_extension("email_confirmation_outbox")
    if isinstance(outbox, list):
        return cast(list[dict[str, str]], outbox)
    set_runtime_extension("email_confirmation_outbox", [])
    return cast(
        list[dict[str, str]], runtime_extension("email_confirmation_outbox", [])
    )


def _confirmation_frontend_url() -> str:
    return str(runtime_config("EMAIL_CONFIRMATION_FRONTEND_URL", "")).strip()


def _build_confirmation_url(token: str) -> str:
    base_url = _confirmation_frontend_url()
    if not base_url:
        runtime_logger().warning(
            "event=auth.email_confirmation_url_missing "
            "EMAIL_CONFIRMATION_FRONTEND_URL is not configured — "
            "confirmation link will be 'n/a'. Set this variable in your environment."
        )
        return "n/a"
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}token={token}"


def _dispatch_confirmation_email(*, email: str, token: str) -> None:
    confirmation_url = _build_confirmation_url(token)
    if runtime_debug_or_testing():
        _confirmation_outbox().append(
            {
                "email": email,
                "token": token,
                "confirmation_url": confirmation_url,
            }
        )
    get_default_email_provider().send(
        EmailMessage(
            to_email=email,
            subject="Confirme sua conta Auraxis",
            html=(
                "<p>Confirme sua conta para concluir a ativacao.</p>"
                f'<p><a href="{confirmation_url}">Confirmar email</a></p>'
            ),
            text=(f"Confirme sua conta Auraxis. Acesse: {confirmation_url}"),
            tag="account_confirmation",
        )
    )
    runtime_logger().info(
        "event=auth.email_confirmation_instructions_dispatched email=%s url_present=%s",
        email,
        bool(_confirmation_frontend_url()),
    )


def issue_email_confirmation(user: User) -> EmailConfirmationResult:
    if user.email_verified_at is not None:
        return EmailConfirmationResult(
            ok=True, message=EMAIL_CONFIRMATION_SUCCESS_MESSAGE
        )

    token = secrets.token_urlsafe(48)
    user.email_verification_token_hash = _token_digest(token)
    user.email_verification_token_expires_at = _utcnow() + timedelta(
        minutes=_token_ttl_minutes()
    )
    user.email_verification_requested_at = _utcnow()
    db.session.commit()

    _dispatch_confirmation_email(email=user.email, token=token)
    runtime_logger().info(
        "event=auth.email_confirmation_requested user_id=%s",
        str(user.id),
    )
    return EmailConfirmationResult(ok=True, message=EMAIL_CONFIRMATION_NEUTRAL_MESSAGE)


def resend_email_confirmation(email: str) -> EmailConfirmationResult:
    normalized_email = email.strip().lower()
    user = cast(User | None, User.query.filter_by(email=normalized_email).first())
    if user is None or user.email_verified_at is not None:
        return EmailConfirmationResult(
            ok=True, message=EMAIL_CONFIRMATION_NEUTRAL_MESSAGE
        )
    return issue_email_confirmation(user)


def confirm_email(*, token: str) -> EmailConfirmationResult:
    digest = _token_digest(token)
    user = cast(
        User | None,
        User.query.filter_by(email_verification_token_hash=digest).first(),
    )
    now = _utcnow()
    if user is None or user.email_verification_token_expires_at is None:
        return EmailConfirmationResult(
            ok=False,
            message=EMAIL_CONFIRMATION_INVALID_TOKEN_MESSAGE,
        )
    expires_at = user.email_verification_token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < now:
        return EmailConfirmationResult(
            ok=False,
            message=EMAIL_CONFIRMATION_INVALID_TOKEN_MESSAGE,
        )

    user.email_verified_at = now
    user.email_verification_token_hash = None
    user.email_verification_token_expires_at = None
    user.email_verification_requested_at = None
    db.session.commit()
    runtime_logger().info(
        "event=auth.email_confirmation_completed user_id=%s",
        str(user.id),
    )
    return EmailConfirmationResult(ok=True, message=EMAIL_CONFIRMATION_SUCCESS_MESSAGE)
