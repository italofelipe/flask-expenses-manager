"""Tests for 'flask ai weekly-insights' CLI command (#1215).

Coverage areas:
- No Premium users: command exits 0, no service calls
- 1 Premium user: service called once, result logged
- N Premium users: each called exactly once
- LLM failure for 1 user: logged as failure, continues to next user
- LLM failure for all users: exits with code 1
- Idempotency: user already has weekly summary today → skipped
- --dry-run flag: prints count without calling service
- Deleted/anonymised users are excluded
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from click.testing import CliRunner

from app.services.llm_provider import LLMProviderError, LLMResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BRT = timezone(timedelta(hours=-3))


def _make_stub_response() -> LLMResponse:
    return LLMResponse(
        content="Briefing semanal stub",
        prompt_tokens=50,
        completion_tokens=100,
        total_tokens=150,
        model="stub",
        latency_ms=10,
    )


def _grant_advanced_simulations(app, user_id: uuid.UUID) -> None:
    with app.app_context():
        from app.extensions.database import db
        from app.models.entitlement import Entitlement, EntitlementSource

        ent = Entitlement(
            user_id=user_id,
            feature_key="advanced_simulations",
            source=EntitlementSource.MANUAL,
            expires_at=None,
        )
        db.session.add(ent)
        db.session.commit()


def _create_user(app) -> uuid.UUID:
    """Create and return a user_id via the registration endpoint."""
    with app.app_context():
        from app.extensions.database import db
        from app.models.account import Account
        from app.models.user import User

        uid = uuid.uuid4()
        u = User(
            id=uid,
            name="Weekly Test User",
            email=f"weekly-{uid.hex[:8]}@test.com",
            password="x",
        )
        db.session.add(u)
        acct = Account(user_id=uid, name="Main", account_type="checking")
        db.session.add(acct)
        db.session.commit()
        return uid


def _log_weekly_summary_today(app, user_id: uuid.UUID) -> None:
    """Simulate that a weekly summary was already generated today."""
    with app.app_context():
        from app.extensions.database import db
        from app.models.llm_audit_log import LLMAuditLog

        log = LLMAuditLog(
            user_id=user_id,
            endpoint="weekly_summary_batch",
            model="stub",
            prompt="test",
            response_text="ok",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            estimated_cost_usd=0.0,
            latency_ms=0,
        )
        db.session.add(log)
        db.session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWeeklyInsightsCLI:
    def _invoke(self, app, *args: str) -> object:
        from app.cli.ai_insights_cli import ai_insights_cli

        runner = CliRunner()
        with app.app_context():
            result = runner.invoke(ai_insights_cli, ["weekly-insights", *args])
        return result

    def test_no_premium_users_exits_zero(self, app) -> None:
        result = self._invoke(app)
        assert result.exit_code == 0
        assert "0" in result.output  # processed=0 or similar

    def test_single_premium_user_called_once(self, app) -> None:
        user_id = _create_user(app)
        _grant_advanced_simulations(app, user_id)

        with patch(
            "app.services.ai_advisory_service.AIAdvisoryService"
            ".generate_weekly_summary_narrative",
            return_value={
                "narrative": "ok",
                "tokens_used": 150,
                "cost_usd": 0.00002,
                "summary": {},
                "model": "stub",
            },
        ) as mock_gen:
            result = self._invoke(app)

        assert result.exit_code == 0
        assert mock_gen.call_count == 1
        assert "processed=1" in result.output
        assert "failures=0" in result.output

    def test_multiple_premium_users_each_called_once(self, app) -> None:
        user_ids = [_create_user(app) for _ in range(3)]
        for uid in user_ids:
            _grant_advanced_simulations(app, uid)

        with patch(
            "app.services.ai_advisory_service.AIAdvisoryService"
            ".generate_weekly_summary_narrative",
            return_value={
                "narrative": "ok",
                "tokens_used": 150,
                "cost_usd": 0.00002,
                "summary": {},
                "model": "stub",
            },
        ) as mock_gen:
            result = self._invoke(app)

        assert result.exit_code == 0
        assert mock_gen.call_count == 3
        assert "processed=3" in result.output

    def test_llm_failure_for_one_user_continues_and_counts_failure(self, app) -> None:
        user_a = _create_user(app)
        user_b = _create_user(app)
        _grant_advanced_simulations(app, user_a)
        _grant_advanced_simulations(app, user_b)

        call_count = 0

        def _side_effect(*a, **kw):  # noqa: ANN202
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMProviderError("LLM down")
            return {
                "narrative": "ok",
                "tokens_used": 100,
                "cost_usd": 0.0,
                "summary": {},
                "model": "stub",
            }

        with patch(
            "app.services.ai_advisory_service.AIAdvisoryService"
            ".generate_weekly_summary_narrative",
            side_effect=_side_effect,
        ):
            result = self._invoke(app)

        # Partial success: one failed, one ok — exit 0 still acceptable,
        # but failures must be reported.
        assert "failures=1" in result.output
        assert "processed=1" in result.output

    def test_all_users_fail_exits_nonzero(self, app) -> None:
        user_id = _create_user(app)
        _grant_advanced_simulations(app, user_id)

        with patch(
            "app.services.ai_advisory_service.AIAdvisoryService"
            ".generate_weekly_summary_narrative",
            side_effect=LLMProviderError("total failure"),
        ):
            result = self._invoke(app)

        assert result.exit_code != 0
        assert "failures=1" in result.output

    def test_idempotency_already_run_today_skips_user(self, app) -> None:
        user_id = _create_user(app)
        _grant_advanced_simulations(app, user_id)
        _log_weekly_summary_today(app, user_id)

        with patch(
            "app.services.ai_advisory_service.AIAdvisoryService"
            ".generate_weekly_summary_narrative",
        ) as mock_gen:
            result = self._invoke(app)

        assert result.exit_code == 0
        assert mock_gen.call_count == 0
        assert "skipped=1" in result.output

    def test_dry_run_prints_count_without_calling_service(self, app) -> None:
        user_id = _create_user(app)
        _grant_advanced_simulations(app, user_id)

        with patch(
            "app.services.ai_advisory_service.AIAdvisoryService"
            ".generate_weekly_summary_narrative",
        ) as mock_gen:
            result = self._invoke(app, "--dry-run")

        assert result.exit_code == 0
        assert mock_gen.call_count == 0
        assert "dry-run" in result.output.lower() or "dry_run" in result.output.lower()

    def test_deleted_users_excluded(self, app) -> None:
        user_id = _create_user(app)
        _grant_advanced_simulations(app, user_id)

        with app.app_context():
            from app.extensions.database import db
            from app.models.user import User

            User.query.filter_by(id=user_id).update(
                {"deleted_at": datetime.now(timezone.utc)}
            )
            db.session.commit()

        with patch(
            "app.services.ai_advisory_service.AIAdvisoryService"
            ".generate_weekly_summary_narrative",
        ) as mock_gen:
            self._invoke(app)

        assert mock_gen.call_count == 0
