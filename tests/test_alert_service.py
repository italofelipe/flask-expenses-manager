"""Unit tests for app/services/alert_service.py."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.extensions.database import db
from app.models.alert import AlertStatus
from app.models.user import User
from app.services.alert_service import (
    AlertServiceError,
    delete_alert,
    dispatch_alert,
    get_preferences,
    get_user_alerts,
    mark_read,
    upsert_preference,
)


def _create_user(app_context: Any) -> User:
    user = User(
        id=uuid.uuid4(),
        name="Test User",
        email=f"alert-test-{uuid.uuid4().hex[:8]}@example.com",
        password="hashed-password",
    )
    db.session.add(user)
    db.session.commit()
    return user


class TestAlertServiceError:
    def test_default_code_and_status(self):
        err = AlertServiceError("something went wrong")
        assert err.code == "ALERT_ERROR"
        assert err.status_code == 400
        assert err.details == {}
        assert str(err) == "something went wrong"

    def test_custom_code_status_and_details(self):
        err = AlertServiceError(
            "not found",
            code="NOT_FOUND",
            status_code=404,
            details={"id": "abc"},
        )
        assert err.code == "NOT_FOUND"
        assert err.status_code == 404
        assert err.details == {"id": "abc"}


class TestDispatchAlert:
    def test_raises_for_unknown_alert_type(self, app):
        with app.app_context():
            user = _create_user(app)
            with pytest.raises(AlertServiceError) as exc_info:
                dispatch_alert(user.id, "nonexistent_type")
            assert exc_info.value.code == "UNKNOWN_ALERT_TYPE"

    def test_returns_none_when_global_opt_out(self, app):
        with app.app_context():
            user = _create_user(app)
            upsert_preference(user.id, "wallet", enabled=True, global_opt_out=True)
            result = dispatch_alert(user.id, "balance_low")
            assert result is None

    def test_returns_none_when_category_disabled(self, app):
        with app.app_context():
            user = _create_user(app)
            upsert_preference(user.id, "wallet", enabled=False)
            result = dispatch_alert(user.id, "balance_low")
            assert result is None

    def test_creates_alert_when_no_preference(self, app):
        with app.app_context():
            user = _create_user(app)
            alert = dispatch_alert(user.id, "balance_low")
            assert alert is not None
            assert alert.user_id == user.id
            assert alert.category == "wallet"
            assert alert.status == AlertStatus.PENDING

    def test_creates_alert_when_preference_enabled(self, app):
        with app.app_context():
            user = _create_user(app)
            upsert_preference(user.id, "wallet", enabled=True)
            ctx = {"entity_type": "tx"}
            alert = dispatch_alert(user.id, "balance_low", context=ctx)
            assert alert is not None
            assert alert.entity_type == "tx"

    def test_passes_context_fields_to_alert(self, app):
        with app.app_context():
            user = _create_user(app)
            entity_id = uuid.uuid4()
            alert = dispatch_alert(
                user.id,
                "goal_deadline",
                context={"entity_type": "goal", "entity_id": entity_id},
            )
            assert alert is not None
            assert alert.entity_type == "goal"


class TestGetUserAlerts:
    def test_returns_empty_list_when_no_alerts(self, app):
        with app.app_context():
            user = _create_user(app)
            alerts = get_user_alerts(user.id)
            assert alerts == []

    def test_returns_all_alerts(self, app):
        with app.app_context():
            user = _create_user(app)
            dispatch_alert(user.id, "balance_low")
            dispatch_alert(user.id, "goal_deadline")
            alerts = get_user_alerts(user.id)
            assert len(alerts) == 2

    def test_unread_only_filters_pending(self, app):
        with app.app_context():
            user = _create_user(app)
            alert = dispatch_alert(user.id, "balance_low")
            assert alert is not None
            mark_read(alert.id, user.id)
            dispatch_alert(user.id, "goal_deadline")
            unread = get_user_alerts(user.id, unread_only=True)
            assert len(unread) == 1
            assert unread[0].status == AlertStatus.PENDING


class TestMarkRead:
    def test_marks_alert_as_sent(self, app):
        with app.app_context():
            user = _create_user(app)
            alert = dispatch_alert(user.id, "balance_low")
            assert alert is not None
            updated = mark_read(alert.id, user.id)
            assert updated.status == AlertStatus.SENT
            assert updated.sent_at is not None

    def test_raises_not_found_for_nonexistent_alert(self, app):
        with app.app_context():
            user = _create_user(app)
            with pytest.raises(AlertServiceError) as exc_info:
                mark_read(uuid.uuid4(), user.id)
            assert exc_info.value.code == "NOT_FOUND"
            assert exc_info.value.status_code == 404

    def test_raises_forbidden_for_wrong_user(self, app):
        with app.app_context():
            owner = _create_user(app)
            other = _create_user(app)
            alert = dispatch_alert(owner.id, "balance_low")
            assert alert is not None
            with pytest.raises(AlertServiceError) as exc_info:
                mark_read(alert.id, other.id)
            assert exc_info.value.code == "FORBIDDEN"
            assert exc_info.value.status_code == 403


class TestDeleteAlert:
    def test_deletes_alert_successfully(self, app):
        with app.app_context():
            user = _create_user(app)
            alert = dispatch_alert(user.id, "balance_low")
            assert alert is not None
            delete_alert(alert.id, user.id)
            remaining = get_user_alerts(user.id)
            assert remaining == []

    def test_raises_not_found_for_nonexistent_alert(self, app):
        with app.app_context():
            user = _create_user(app)
            with pytest.raises(AlertServiceError) as exc_info:
                delete_alert(uuid.uuid4(), user.id)
            assert exc_info.value.code == "NOT_FOUND"
            assert exc_info.value.status_code == 404

    def test_raises_forbidden_for_wrong_user(self, app):
        with app.app_context():
            owner = _create_user(app)
            other = _create_user(app)
            alert = dispatch_alert(owner.id, "balance_low")
            assert alert is not None
            with pytest.raises(AlertServiceError) as exc_info:
                delete_alert(alert.id, other.id)
            assert exc_info.value.code == "FORBIDDEN"
            assert exc_info.value.status_code == 403


class TestPreferences:
    def test_get_preferences_returns_empty_list(self, app):
        with app.app_context():
            user = _create_user(app)
            assert get_preferences(user.id) == []

    def test_upsert_creates_new_preference(self, app):
        with app.app_context():
            user = _create_user(app)
            pref = upsert_preference(user.id, "wallet", enabled=True)
            assert pref.enabled is True
            assert pref.global_opt_out is False
            assert pref.category == "wallet"

    def test_upsert_updates_existing_preference(self, app):
        with app.app_context():
            user = _create_user(app)
            upsert_preference(user.id, "wallet", enabled=True)
            upsert_preference(user.id, "wallet", enabled=False, global_opt_out=True)
            prefs = get_preferences(user.id)
            assert len(prefs) == 1
            assert prefs[0].enabled is False
            assert prefs[0].global_opt_out is True

    def test_get_preferences_returns_sorted_by_category(self, app):
        with app.app_context():
            user = _create_user(app)
            upsert_preference(user.id, "wallet", enabled=True)
            upsert_preference(user.id, "goals", enabled=False)
            prefs = get_preferences(user.id)
            categories = [p.category for p in prefs]
            assert categories == sorted(categories)
