"""Tests for AI Insight audit preview admin endpoints (#1311)."""

from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

_TEST_ENV = {
    "SECRET_KEY": "test-secret-key-with-64-chars-minimum-for-jwt-signing-0001",
    "JWT_SECRET_KEY": "test-jwt-secret-key-with-64-chars-minimum-for-signing-0002",
    "FLASK_TESTING": "true",
    "SECURITY_ENFORCE_STRONG_SECRETS": "false",
    "DOCS_EXPOSURE_POLICY": "public",
    "CORS_ALLOWED_ORIGINS": "https://frontend.local",
    "GRAPHQL_ALLOW_INTROSPECTION": "true",
}


@pytest.fixture()
def admin_preview_app(tmp_path: Path):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.sqlite3'}"
    for key, value in _TEST_ENV.items():
        os.environ[key] = value

    from app import create_app
    from app.extensions.database import db

    flask_app = create_app(enable_http_runtime=False)
    flask_app.config["TESTING"] = True

    with flask_app.app_context():
        db.drop_all()
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def admin_preview_client(admin_preview_app) -> Generator:
    with admin_preview_app.test_client() as client:
        yield client


def _create_user_with_transactions(app) -> uuid.UUID:
    with app.app_context():
        from app.extensions.database import db
        from app.models.account import Account
        from app.models.transaction import (
            Transaction,
            TransactionCategory,
            TransactionStatus,
            TransactionType,
        )
        from app.models.user import User

        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            name="Audit Preview User",
            email=f"audit-preview-{user_id.hex[:8]}@test.com",
            password="x",
        )
        db.session.add(user)
        account = Account(
            user_id=user_id,
            name="Conta principal",
            account_type="checking",
        )
        db.session.add(account)
        db.session.flush()
        db.session.add_all(
            [
                Transaction(
                    user_id=user_id,
                    account_id=account.id,
                    title="Salário",
                    amount=Decimal("4000.00"),
                    status=TransactionStatus.PAID,
                    type=TransactionType.INCOME,
                    due_date=date(2026, 5, 17),
                    category=TransactionCategory.outros,
                ),
                Transaction(
                    user_id=user_id,
                    account_id=account.id,
                    title="Mercado",
                    amount=Decimal("600.00"),
                    status=TransactionStatus.PAID,
                    type=TransactionType.EXPENSE,
                    due_date=date(2026, 5, 17),
                    category=TransactionCategory.alimentacao,
                ),
            ]
        )
        db.session.commit()
        return user_id


def _data(payload: dict) -> dict:
    return payload.get("data") or payload


def test_deterministic_risks_use_snapshot_financial_health_flags() -> None:
    from app.services.ai_insight_audit import build_deterministic_risks

    snapshot = {
        "financial_health": {
            "risk_flags": [
                {
                    "code": "future_commitment_pressure",
                    "severity": "medium",
                    "dimension": "transactions",
                    "evidence": [
                        "current_period.commitments.pending_expense_total",
                        "current_period.paid.balance",
                    ],
                }
            ]
        }
    }

    assert (
        build_deterministic_risks(snapshot)
        == snapshot["financial_health"]["risk_flags"]
    )


class TestAIInsightAuditPreviewAdmin:
    def test_preview_returns_403_for_non_admin(self, admin_preview_client) -> None:
        with patch(
            "app.controllers.admin.ai_insights._is_admin",
            return_value=False,
        ):
            resp = admin_preview_client.post(
                "/admin/ai-insights/preview",
                json={
                    "user_id": str(uuid.uuid4()),
                    "period_type": "daily",
                    "anchor_date": "2026-05-17",
                },
            )

        assert resp.status_code == 403
        body = resp.get_json()
        assert body["success"] is False
        assert body["error"]["code"] == "FORBIDDEN"

    def test_preview_creates_run_without_llm_or_quota(
        self,
        admin_preview_app,
        admin_preview_client,
    ) -> None:
        user_id = _create_user_with_transactions(admin_preview_app)

        with (
            patch(
                "app.controllers.admin.ai_insights._is_admin",
                return_value=True,
            ),
            patch(
                "app.services.ai_advisory_service.get_llm_provider",
                side_effect=AssertionError("preview must not initialize LLM provider"),
            ),
        ):
            resp = admin_preview_client.post(
                "/admin/ai-insights/preview",
                json={
                    "user_id": str(user_id),
                    "period_type": "daily",
                    "anchor_date": "2026-05-17",
                },
            )

        assert resp.status_code == 201
        payload = _data(resp.get_json())
        assert payload["run_id"]
        assert payload["period_type"] == "daily"
        assert payload["period_label"] == "2026-05-17"
        assert payload["snapshot_hash"]
        assert payload["snapshot"]["period"]["label"] == "2026-05-17"
        assert "comparisons" in payload
        assert isinstance(payload["risks"], list)
        assert isinstance(payload["evidence_manifest"], dict)
        assert payload["data_quality"]["has_transactions"] is True

        with admin_preview_app.app_context():
            from app.models.ai_insight import AIInsight
            from app.models.ai_insight_run import AIInsightRun, AIInsightRunStatus
            from app.models.llm_audit_log import LLMAuditLog

            run = AIInsightRun.query.filter_by(user_id=user_id).one()
            assert str(run.id) == payload["run_id"]
            assert run.status == AIInsightRunStatus.previewed
            assert run.snapshot_hash == payload["snapshot_hash"]
            assert run.tokens_total == 0
            assert LLMAuditLog.query.filter_by(user_id=user_id).count() == 0
            assert AIInsight.query.filter_by(user_id=user_id).count() == 0
