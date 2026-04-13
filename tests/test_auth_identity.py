from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.auth.identity import (
    AuthContext,
    RevokedTokenError,
    auth_context_from_claims,
    get_active_auth_context,
    is_auth_context_revoked,
)
from app.models.user import User


def test_auth_context_from_claims_parses_core_fields() -> None:
    subject = str(uuid4())
    claims = {
        "sub": subject,
        "email": "user@email.com",
        "roles": ["admin", "member"],
        "permissions": ["wallet:read"],
        "jti": "token-123",
        "iat": 1_772_848_800,
        "exp": 1_772_852_400,
    }

    context = auth_context_from_claims(claims)

    assert context == AuthContext(
        subject=subject,
        email="user@email.com",
        roles=("admin", "member"),
        permissions=("wallet:read",),
        jti="token-123",
        issued_at=datetime.fromtimestamp(1_772_848_800, tz=UTC),
        expires_at=datetime.fromtimestamp(1_772_852_400, tz=UTC),
        raw_claims=claims,
    )


def test_is_auth_context_revoked_when_current_jti_differs(app) -> None:
    with app.app_context():
        user = User(name="ctx-user", email="ctx-user@email.com", password="hash")
        user.current_jti = "active-jti"
        from app.extensions.database import db

        db.session.add(user)
        db.session.commit()

        context = AuthContext(
            subject=str(user.id),
            email=user.email,
            roles=(),
            permissions=(),
            jti="stale-jti",
            issued_at=None,
            expires_at=None,
            raw_claims={"sub": str(user.id), "jti": "stale-jti"},
        )

        assert is_auth_context_revoked(context) is True


def test_get_active_auth_context_raises_for_revoked_context(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subject = str(uuid4())
    revoked_context = AuthContext(
        subject=subject,
        email=None,
        roles=(),
        permissions=(),
        jti="revoked-jti",
        issued_at=None,
        expires_at=None,
        raw_claims={"sub": subject, "jti": "revoked-jti"},
    )

    monkeypatch.setattr(
        "app.auth.identity.get_current_auth_context",
        lambda optional=False: revoked_context,
    )
    monkeypatch.setattr(
        "app.auth.identity.is_auth_context_revoked",
        lambda context: True,
    )

    with pytest.raises(RevokedTokenError):
        get_active_auth_context()


def test_is_auth_context_revoked_for_soft_deleted_user(app) -> None:
    """A soft-deleted user's token must be treated as revoked (LGPD)."""
    with app.app_context():
        from app.extensions.database import db
        from app.utils.datetime_utils import utc_now_naive

        user = User(
            name="deleted-user",
            email="deleted-user@email.com",
            password="hash",
        )
        user.current_jti = "valid-jti"
        user.deleted_at = utc_now_naive()
        db.session.add(user)
        db.session.commit()

        context = AuthContext(
            subject=str(user.id),
            email=user.email,
            roles=(),
            permissions=(),
            jti="valid-jti",
            issued_at=None,
            expires_at=None,
            raw_claims={"sub": str(user.id), "jti": "valid-jti"},
        )

        # Even though jti matches, deleted_at must cause revocation.
        assert is_auth_context_revoked(context) is True


def test_jwt_callback_revokes_deleted_user_access_token(app) -> None:
    """Access-token revocation check must treat soft-deleted users as revoked."""
    with app.app_context():
        from app.extensions.database import db
        from app.extensions.jwt_callbacks import _is_access_token_revoked
        from app.utils.datetime_utils import utc_now_naive

        user = User(
            name="deleted-jwt-user",
            email="deleted-jwt@email.com",
            password="hash",
        )
        user.current_jti = "valid-jti-access"
        user.deleted_at = utc_now_naive()
        db.session.add(user)
        db.session.commit()

        # Token matches current_jti but user is soft-deleted — must be revoked.
        result = _is_access_token_revoked(str(user.id), "valid-jti-access")
        assert result is True


def test_jwt_callback_revokes_deleted_user_refresh_token(app) -> None:
    """Refresh-token revocation check must treat soft-deleted users as revoked."""
    with app.app_context():
        from app.extensions.database import db
        from app.extensions.jwt_callbacks import _is_refresh_token_revoked
        from app.utils.datetime_utils import utc_now_naive

        user = User(
            name="deleted-refresh-user",
            email="deleted-refresh@email.com",
            password="hash",
        )
        user.refresh_token_jti = "valid-jti-refresh"
        user.deleted_at = utc_now_naive()
        db.session.add(user)
        db.session.commit()

        result = _is_refresh_token_revoked(str(user.id), "valid-jti-refresh")
        assert result is True
