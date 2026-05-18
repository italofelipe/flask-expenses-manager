"""Tests for AIInsightRun audit persistence and retention (#1310)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.extensions.database import db
from app.models.ai_insight import AIInsight, InsightType
from app.models.ai_insight_run import AIInsightRun, AIInsightRunStatus
from app.services.ai_insight_runs import (
    DEFAULT_AI_INSIGHT_RUN_RETENTION_DAYS,
    create_ai_insight_run,
    purge_expired_ai_insight_runs,
    sanitize_audit_snapshot,
)
from app.utils.datetime_utils import utc_now_naive


def _insight(user_id: uuid.UUID) -> AIInsight:
    return AIInsight(
        user_id=user_id,
        content='{"summary":"Resumo","items":[]}',
        insight_type=InsightType.daily,
        period_label="2026-05-18",
        period_start=date(2026, 5, 18),
        period_end=date(2026, 5, 18),
        model="gpt-4o-mini",
        tokens_used=150,
        cost_usd=Decimal("0.000123"),
    )


def _run_payload(user_id: uuid.UUID) -> dict[str, object]:
    return {
        "user_id": user_id,
        "status": AIInsightRunStatus.generated,
        "period_type": InsightType.daily,
        "period_label": "2026-05-18",
        "period_start": date(2026, 5, 18),
        "period_end": date(2026, 5, 18),
        "snapshot_schema_version": "financial_insight_snapshot.v2",
        "snapshot_hash": "sha256:current",
        "previous_snapshot_hash": "sha256:previous",
        "prompt_template_version": "financial-insight.v2.2026-05-18",
        "snapshot_json": {
            "schema_version": "financial_insight_snapshot.v2",
            "dimensions": {"transactions": {"balance": "100.00"}},
        },
        "evidence_manifest_json": {
            "evidence": {
                "dimensions.transactions.balance": {
                    "label": "Saldo",
                    "value": "100.00",
                }
            }
        },
        "data_quality_json": {"has_transactions": True},
        "rejection_reasons_json": [],
        "truncation_flags_json": {"truncated": False},
        "model": "gpt-4o-mini",
        "tokens_in": 100,
        "tokens_out": 50,
        "tokens_total": 150,
        "cost_usd": Decimal("0.000123"),
    }


class TestAIInsightRunModel:
    def test_create_generated_run_links_to_insight_and_defaults_retention(
        self, app
    ) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            insight = _insight(user_id)
            db.session.add(insight)
            db.session.flush()

            run_payload = _run_payload(user_id)
            run_payload["snapshot_json"] = {
                "user_id": str(user_id),
                "dimensions": {
                    "transactions": {
                        "balance": "100.00",
                        "sample": [
                            {
                                "transaction_id": str(uuid.uuid4()),
                                "title": "Pagamento maria@example.com",
                            }
                        ],
                    }
                },
            }
            run = create_ai_insight_run(
                **run_payload,
                ai_insight_id=insight.id,
            )

            fetched = db.session.get(AIInsightRun, run.id)
            assert fetched is not None
            assert fetched.ai_insight_id == insight.id
            assert fetched.status == AIInsightRunStatus.generated
            assert fetched.period_type == InsightType.daily
            assert fetched.snapshot_hash == "sha256:current"
            assert fetched.previous_snapshot_hash == "sha256:previous"
            assert fetched.prompt_template_version == "financial-insight.v2.2026-05-18"
            assert fetched.snapshot_json["dimensions"]["transactions"]["balance"] == (
                "100.00"
            )
            assert "user_id" not in fetched.snapshot_json
            sample = fetched.snapshot_json["dimensions"]["transactions"]["sample"][0]
            assert "transaction_id" not in sample
            assert sample["title"] == "Pagamento [email]"
            assert fetched.evidence_manifest_json["evidence"]
            assert fetched.tokens_in == 100
            assert fetched.tokens_out == 50
            assert fetched.tokens_total == 150
            assert fetched.cost_usd == Decimal("0.000123")
            assert fetched.expires_at is not None
            retention_delta = fetched.expires_at - fetched.created_at
            assert (
                timedelta(days=29, hours=23)
                <= retention_delta
                <= timedelta(days=30, hours=1)
            )
            assert DEFAULT_AI_INSIGHT_RUN_RETENTION_DAYS == 30

    def test_sanitize_audit_snapshot_removes_identifiers_and_redacts_free_text(
        self,
    ) -> None:
        raw = {
            "user_id": str(uuid.uuid4()),
            "email": "cliente@example.com",
            "external_id": "bank-tx-123",
            "dimensions": {
                "transactions": {
                    "sample": [
                        {
                            "transaction_id": str(uuid.uuid4()),
                            "title": "Consulta CPF 123.456.789-10",
                            "description": "Pagamento para maria@example.com",
                            "amount": "100.00",
                        }
                    ]
                }
            },
        }

        sanitized = sanitize_audit_snapshot(raw)

        assert "user_id" not in sanitized
        assert "email" not in sanitized
        assert "external_id" not in sanitized
        sample = sanitized["dimensions"]["transactions"]["sample"][0]
        assert "transaction_id" not in sample
        assert sample["title"] == "Consulta CPF [cpf]"
        assert sample["description"] == "Pagamento para [email]"
        assert sample["amount"] == "100.00"

    def test_purge_expired_runs_clears_audit_payload_but_keeps_metadata(
        self, app
    ) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            now = utc_now_naive()
            expired = AIInsightRun(
                **_run_payload(user_id),
                expires_at=now - timedelta(seconds=1),
            )
            fresh_payload = _run_payload(user_id)
            fresh_payload["snapshot_hash"] = "sha256:fresh"
            fresh = AIInsightRun(
                **fresh_payload,
                expires_at=now + timedelta(days=1),
            )
            db.session.add_all([expired, fresh])
            db.session.commit()

            deleted = purge_expired_ai_insight_runs(now=now)

            assert deleted == 1
            db.session.refresh(expired)
            db.session.refresh(fresh)
            assert expired.status == AIInsightRunStatus.purged
            assert expired.snapshot_json is None
            assert expired.evidence_manifest_json is None
            assert expired.purged_at == now
            assert expired.snapshot_hash == "sha256:current"
            assert fresh.snapshot_json is not None
            assert fresh.evidence_manifest_json is not None
            assert fresh.purged_at is None
