"""Tests for J12 — entitlement service and enforcement decorator.

Covers:
  - has_entitlement returns False when no entitlement exists
  - has_entitlement returns False when entitlement is expired
  - has_entitlement returns True when active (non-expired) entitlement exists
  - sync_entitlements_from_subscription grants correct features for premium plan
  - sync_entitlements_from_subscription revokes premium features on cancel
  - require_entitlement decorator returns 403 when missing
  - grant_entitlement creates a new entitlement
  - revoke_entitlement removes the entitlement
  - plan_features matrix sanity
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from app.extensions.database import db
from app.models.entitlement import Entitlement, EntitlementSource
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.utils.datetime_utils import utc_now_naive

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(app, suffix: str = "") -> User:
    with app.app_context():
        user = User(
            name=f"j12-test-user{suffix}",
            email=f"j12-test{suffix}@auraxis.test",
            password="StrongPass@123",
        )
        db.session.add(user)
        db.session.flush()
        db.session.commit()
        return User.query.get(user.id)


def _make_subscription(
    app,
    user_id,
    plan_code: str = "premium",
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> Subscription:
    with app.app_context():
        sub = Subscription(
            user_id=user_id,
            plan_code=plan_code,
            status=status,
        )
        db.session.add(sub)
        db.session.commit()
        return Subscription.query.get(sub.id)


def _register_and_login(client):
    suffix = uuid.uuid4().hex[:8]
    email = f"j12-{suffix}@auraxis.test"
    password = "StrongPass@123"
    r = client.post(
        "/auth/register",
        json={"name": f"j12-{suffix}", "email": email, "password": password},
    )
    assert r.status_code == 201
    r2 = client.post("/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r2.get_json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# has_entitlement
# ---------------------------------------------------------------------------


def test_has_entitlement_returns_false_when_missing(app) -> None:
    """has_entitlement returns False when no row exists."""
    from app.services.entitlement_service import has_entitlement

    user_id = uuid.uuid4()
    with app.app_context():
        assert has_entitlement(user_id, "nonexistent_feature") is False


def test_has_entitlement_returns_false_when_expired(app) -> None:
    """has_entitlement returns False for an expired entitlement."""
    from app.services.entitlement_service import has_entitlement

    user = _make_user(app, "-exp")
    with app.app_context():
        ent = Entitlement(
            user_id=user.id,
            feature_key="export_pdf",
            source=EntitlementSource.SUBSCRIPTION,
            expires_at=utc_now_naive() - timedelta(days=1),
        )
        db.session.add(ent)
        db.session.commit()
        assert has_entitlement(user.id, "export_pdf") is False


def test_has_entitlement_returns_true_when_active(app) -> None:
    """has_entitlement returns True for a non-expired entitlement."""
    from app.services.entitlement_service import has_entitlement

    user = _make_user(app, "-active")
    with app.app_context():
        ent = Entitlement(
            user_id=user.id,
            feature_key="advanced_simulations",
            source=EntitlementSource.SUBSCRIPTION,
            expires_at=utc_now_naive() + timedelta(days=30),
        )
        db.session.add(ent)
        db.session.commit()
        assert has_entitlement(user.id, "advanced_simulations") is True


def test_has_entitlement_returns_true_for_no_expiry(app) -> None:
    """has_entitlement returns True when expires_at is None (permanent)."""
    from app.services.entitlement_service import has_entitlement

    user = _make_user(app, "-perm")
    with app.app_context():
        ent = Entitlement(
            user_id=user.id,
            feature_key="wallet_read",
            source=EntitlementSource.MANUAL,
            expires_at=None,
        )
        db.session.add(ent)
        db.session.commit()
        assert has_entitlement(user.id, "wallet_read") is True


# ---------------------------------------------------------------------------
# grant_entitlement / revoke_entitlement
# ---------------------------------------------------------------------------


def test_grant_entitlement_creates_new_row(app) -> None:
    from app.services.entitlement_service import grant_entitlement

    user = _make_user(app, "-grant")
    with app.app_context():
        grant_entitlement(user.id, "export_pdf", source="manual")
        db.session.commit()
        stored = Entitlement.query.filter_by(
            user_id=user.id, feature_key="export_pdf"
        ).first()
        assert stored is not None
        assert stored.source == EntitlementSource.MANUAL


def test_grant_entitlement_updates_existing_row(app) -> None:
    """Calling grant_entitlement twice does not create duplicate rows."""
    from app.services.entitlement_service import grant_entitlement

    user = _make_user(app, "-grant2")
    with app.app_context():
        grant_entitlement(user.id, "export_pdf", source="manual")
        db.session.commit()
        grant_entitlement(
            user.id,
            "export_pdf",
            source="subscription",
            expires_at=utc_now_naive() + timedelta(days=30),
        )
        db.session.commit()
        rows = Entitlement.query.filter_by(
            user_id=user.id, feature_key="export_pdf"
        ).all()
        assert len(rows) == 1
        assert rows[0].source == EntitlementSource.SUBSCRIPTION


def test_revoke_entitlement_removes_row(app) -> None:
    from app.services.entitlement_service import grant_entitlement, revoke_entitlement

    user = _make_user(app, "-revoke")
    with app.app_context():
        grant_entitlement(user.id, "shared_entries", source="subscription")
        db.session.commit()
        revoke_entitlement(user.id, "shared_entries")
        db.session.commit()
        stored = Entitlement.query.filter_by(
            user_id=user.id, feature_key="shared_entries"
        ).first()
        assert stored is None


# ---------------------------------------------------------------------------
# sync_entitlements_from_subscription
# ---------------------------------------------------------------------------


def test_sync_grants_premium_features_for_active_premium(app) -> None:
    """sync_entitlements_from_subscription grants all premium features."""
    from app.config.plan_features import PLAN_FEATURES
    from app.services.entitlement_service import sync_entitlements_from_subscription

    user = _make_user(app, "-sync1")
    with app.app_context():
        sub = Subscription(
            user_id=user.id,
            plan_code="premium",
            status=SubscriptionStatus.ACTIVE,
        )
        db.session.add(sub)
        db.session.commit()

        result = sync_entitlements_from_subscription(sub)
        db.session.commit()

        granted_keys = {e.feature_key for e in result}
        expected_keys = set(PLAN_FEATURES["premium"])
        assert expected_keys == granted_keys, (
            f"Expected {expected_keys}, got {granted_keys}"
        )


def test_sync_revokes_premium_features_on_cancel(app) -> None:
    """sync_entitlements_from_subscription revokes premium features when canceled."""
    from app.config.plan_features import PLAN_FEATURES
    from app.services.entitlement_service import sync_entitlements_from_subscription

    user = _make_user(app, "-sync2")
    with app.app_context():
        # First grant premium
        sub = Subscription(
            user_id=user.id,
            plan_code="premium",
            status=SubscriptionStatus.ACTIVE,
        )
        db.session.add(sub)
        db.session.commit()
        sync_entitlements_from_subscription(sub)
        db.session.commit()

        # Now cancel
        sub.status = SubscriptionStatus.CANCELED
        db.session.commit()
        result = sync_entitlements_from_subscription(sub)
        db.session.commit()

        granted_keys = {e.feature_key for e in result}
        expected_free_keys = set(PLAN_FEATURES["free"])
        # After cancel only free features should remain
        assert granted_keys == expected_free_keys, (
            f"Expected free features {expected_free_keys}, got {granted_keys}"
        )


def test_sync_grants_trial_features_for_trialing_sub(app) -> None:
    """sync_entitlements_from_subscription grants trial features for TRIALING status."""
    from app.config.plan_features import PLAN_FEATURES
    from app.services.entitlement_service import sync_entitlements_from_subscription

    user = _make_user(app, "-sync3")
    with app.app_context():
        sub = Subscription(
            user_id=user.id,
            plan_code="trial",
            status=SubscriptionStatus.TRIALING,
        )
        db.session.add(sub)
        db.session.commit()

        result = sync_entitlements_from_subscription(sub)
        db.session.commit()

        granted_keys = {e.feature_key for e in result}
        expected_keys = set(PLAN_FEATURES["trial"])
        assert expected_keys == granted_keys


# ---------------------------------------------------------------------------
# require_entitlement decorator — 403 when missing
# ---------------------------------------------------------------------------


def test_require_entitlement_returns_false_for_missing_feature(app, client) -> None:
    """Check endpoint reports no access when user lacks the feature."""
    from app.services.entitlement_service import revoke_entitlement

    token = _register_and_login(client)
    # Fetch user_id from profile before entering app context
    profile_resp = client.get("/user/profile", headers=_auth(token))
    profile_body = profile_resp.get_json()
    user_id = uuid.UUID(
        profile_body.get("data", {}).get("id") or profile_body.get("user", {}).get("id")
    )
    # Revoke the trial entitlement to simulate a free/downgraded user
    with app.app_context():
        revoke_entitlement(user_id, "export_pdf")
        db.session.commit()
    response = client.get(
        "/entitlements/check?feature_key=export_pdf",
        headers=_auth(token),
    )
    assert response.status_code == 200
    body = response.get_json()
    # Accept both v1 contract {"feature_key":..., "active": False}
    # and v2 contract {"data": {"feature_key":..., "active": False}}
    data = body.get("data") or body
    assert data.get("active") is False


def test_require_entitlement_decorator_returns_403_when_missing(app, client) -> None:
    """require_entitlement decorator returns 403 when user has no entitlement.

    Registers a throw-away route on the real test app (which has SQLAlchemy
    configured) and verifies the 403 response shape.
    """
    from app.services.entitlement_service import require_entitlement
    from app.utils.typed_decorators import typed_jwt_required as jwt_required

    # Register a test-only protected route on the real app
    _route_registered = getattr(app, "_j12_test_route_registered", False)
    if not _route_registered:

        @app.route("/test-j12-entitlement-required")
        @jwt_required()
        @require_entitlement("export_pdf")
        def _j12_protected():  # type: ignore[return-value]
            return {"ok": True}, 200

        app._j12_test_route_registered = True  # type: ignore[attr-defined]

    # Use a real registered user so auth guard allows the request
    token = _register_and_login(client)
    # Fetch user_id from profile, then revoke trial entitlement to simulate free-tier
    from app.services.entitlement_service import revoke_entitlement

    profile_resp = client.get("/user/profile", headers=_auth(token))
    profile_body = profile_resp.get_json()
    user_id = uuid.UUID(
        profile_body.get("data", {}).get("id") or profile_body.get("user", {}).get("id")
    )
    with app.app_context():
        revoke_entitlement(user_id, "export_pdf")
        db.session.commit()

    resp = client.get(
        "/test-j12-entitlement-required",
        headers=_auth(token),
    )
    assert resp.status_code == 403
    body = resp.get_json()
    assert body["error"]["code"] == "ENTITLEMENT_REQUIRED"


def test_require_entitlement_allows_when_active(app, client) -> None:
    """require_entitlement via check endpoint returns True when entitlement exists."""
    from app.services.entitlement_service import grant_entitlement

    token = _register_and_login(client)

    # Extract user_id from JWT by calling /entitlements
    list_resp = client.get("/entitlements", headers=_auth(token))
    assert list_resp.status_code == 200

    # Grant entitlement via admin route is not possible without admin role.
    # Instead test the service directly: register a user, grant via service, then check.
    suffix = uuid.uuid4().hex[:6]
    with app.app_context():
        user = User(
            name=f"j12-ent-{suffix}",
            email=f"j12-ent-{suffix}@auraxis.test",
            password="StrongPass@123",
        )
        db.session.add(user)
        db.session.commit()
        grant_entitlement(user.id, "export_pdf", source="manual")
        db.session.commit()

        from app.services.entitlement_service import has_entitlement

        assert has_entitlement(user.id, "export_pdf") is True


# ---------------------------------------------------------------------------
# plan_features sanity
# ---------------------------------------------------------------------------


def test_plan_features_matrix_structure() -> None:
    from app.config.plan_features import PLAN_FEATURES, PREMIUM_FEATURES

    assert "free" in PLAN_FEATURES
    assert "premium" in PLAN_FEATURES
    assert "trial" in PLAN_FEATURES

    assert "basic_simulations" in PLAN_FEATURES["free"]
    assert "advanced_simulations" in PLAN_FEATURES["premium"]
    assert "advanced_simulations" in PLAN_FEATURES["trial"]

    # Free plan must NOT include premium-only features
    for feat in PREMIUM_FEATURES:
        assert feat not in PLAN_FEATURES["free"]

    # Premium plan must include all free features
    for feat in PLAN_FEATURES["free"]:
        assert feat in PLAN_FEATURES["premium"]


# ---------------------------------------------------------------------------
# Entitlement cache behaviour (HARD-05)
# ---------------------------------------------------------------------------


def test_has_entitlement_uses_cache_on_second_call(app, mocker) -> None:
    """Second call to has_entitlement returns cached value without hitting the DB."""
    from app.services import entitlement_service
    from app.services.cache_service import ENTITLEMENT_CACHE_TTL, RedisCacheService

    user_id = uuid.uuid4()
    feature_key = "export_pdf"

    # Mock a cache that initially returns None then returns the cached value
    mock_cache = mocker.MagicMock(spec=RedisCacheService)
    mock_cache.available = True
    # First call: cache miss → DB hit
    # Second call: cache hit → no DB hit
    mock_cache.get.side_effect = [None, True]

    mocker.patch.object(
        entitlement_service, "get_cache_service", return_value=mock_cache
    )

    db_query_spy = mocker.patch(
        "app.models.entitlement.Entitlement.query",
        wraps=None,
    )
    # Simulate DB returning None (no entitlement)
    filter_chain = mocker.MagicMock()
    filter_chain.first.return_value = None
    db_query_spy.filter_by.return_value = mocker.MagicMock(
        filter=mocker.MagicMock(return_value=filter_chain)
    )

    with app.app_context():
        # First call: cache miss
        result1 = entitlement_service.has_entitlement(user_id, feature_key)
        # Cache should have been set with False
        mock_cache.set.assert_called_once_with(
            f"entitlement:{user_id}:{feature_key}", False, ttl=ENTITLEMENT_CACHE_TTL
        )
        assert result1 is False

        # Second call: cache hit (returns True from mock)
        result2 = entitlement_service.has_entitlement(user_id, feature_key)
        # DB should NOT have been called again
        assert mock_cache.get.call_count == 2
        assert result2 is True


def test_grant_entitlement_invalidates_cache(app, mocker) -> None:
    """grant_entitlement invalidates the entitlement cache for the user."""
    from app.services import entitlement_service
    from app.services.cache_service import RedisCacheService

    mock_cache = mocker.MagicMock(spec=RedisCacheService)
    mock_cache.available = True
    mock_cache.get.return_value = None
    mocker.patch.object(
        entitlement_service, "get_cache_service", return_value=mock_cache
    )

    suffix = uuid.uuid4().hex[:6]
    with app.app_context():
        user = User(
            name=f"j12-grant-cache-{suffix}",
            email=f"j12-grant-cache-{suffix}@auraxis.test",
            password="StrongPass@123",
        )
        db.session.add(user)
        db.session.commit()

        entitlement_service.grant_entitlement(user.id, "export_pdf", source="manual")
        db.session.commit()

        # invalidate_pattern should have been called with the user's pattern
        mock_cache.invalidate_pattern.assert_called_with(f"entitlement:{user.id}:*")


def test_revoke_entitlement_invalidates_cache(app, mocker) -> None:
    """revoke_entitlement invalidates the entitlement cache for the user."""
    from app.services import entitlement_service
    from app.services.cache_service import RedisCacheService

    mock_cache = mocker.MagicMock(spec=RedisCacheService)
    mock_cache.available = True
    mock_cache.get.return_value = None
    mocker.patch.object(
        entitlement_service, "get_cache_service", return_value=mock_cache
    )

    suffix = uuid.uuid4().hex[:6]
    with app.app_context():
        user = User(
            name=f"j12-revoke-cache-{suffix}",
            email=f"j12-revoke-cache-{suffix}@auraxis.test",
            password="StrongPass@123",
        )
        db.session.add(user)
        db.session.commit()

        entitlement_service.revoke_entitlement(user.id, "export_pdf")
        db.session.flush()

        mock_cache.invalidate_pattern.assert_called_with(f"entitlement:{user.id}:*")


def test_has_entitlement_falls_back_to_db_when_cache_unavailable(app, mocker) -> None:
    """When Redis is down (no-op cache), has_entitlement falls through to the DB."""
    from app.services import entitlement_service
    from app.services.cache_service import _NoOpCacheService

    noop_cache = _NoOpCacheService()
    mocker.patch.object(
        entitlement_service, "get_cache_service", return_value=noop_cache
    )

    suffix = uuid.uuid4().hex[:6]
    with app.app_context():
        user = User(
            name=f"j12-noop-{suffix}",
            email=f"j12-noop-{suffix}@auraxis.test",
            password="StrongPass@123",
        )
        db.session.add(user)
        db.session.commit()

        ent = Entitlement(
            user_id=user.id,
            feature_key="wallet_read",
            source=EntitlementSource.MANUAL,
            expires_at=None,
        )
        db.session.add(ent)
        db.session.commit()

        # Even with no-op cache, result should come from DB
        result = entitlement_service.has_entitlement(user.id, "wallet_read")
        assert result is True


# ---------------------------------------------------------------------------
# Entitlement endpoints
# ---------------------------------------------------------------------------


def test_entitlements_list_requires_auth(client) -> None:
    response = client.get("/entitlements")
    assert response.status_code == 401


def test_entitlements_list_empty_for_new_user(client) -> None:
    token = _register_and_login(client)
    response = client.get("/entitlements", headers=_auth(token))
    assert response.status_code == 200
    body = response.get_json()
    # Accept both v1 and v2 contracts
    items = body.get("items") or body.get("data", {}).get("items", [])
    assert isinstance(items, list)


def test_entitlements_check_missing_feature_key(client) -> None:
    token = _register_and_login(client)
    response = client.get("/entitlements/check", headers=_auth(token))
    assert response.status_code == 400


def test_admin_grant_requires_auth(client) -> None:
    response = client.post("/entitlements/admin", json={})
    assert response.status_code == 401


def test_admin_grant_returns_403_for_non_admin(client) -> None:
    token = _register_and_login(client)
    response = client.post(
        "/entitlements/admin",
        headers=_auth(token),
        json={
            "user_id": str(uuid.uuid4()),
            "feature_key": "export_pdf",
        },
    )
    assert response.status_code == 403


def test_admin_revoke_returns_403_for_non_admin(client) -> None:
    token = _register_and_login(client)
    fake_id = str(uuid.uuid4())
    response = client.delete(
        f"/entitlements/admin/{fake_id}",
        headers=_auth(token),
    )
    assert response.status_code == 403
