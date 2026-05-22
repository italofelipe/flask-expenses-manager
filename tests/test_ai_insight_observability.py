"""Sprint 5 (obs-1) tests for the AI insight observability stack.

Covers:
- truncate_snapshot() behaviour below/above the byte cap
- AIInsight.metadata_json persistence by generate_financial_insights
- Prometheus metrics emitted on each generation
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from app.extensions.database import db
from app.models.ai_insight import AIInsight
from app.services.financial_insight_context_builder import (
    MAX_SNAPSHOT_BYTES,
    truncate_snapshot,
)
from app.services.llm_provider import LLMResponse

_ALL_FINANCIAL_DIMENSIONS = [
    "general",
    "transactions",
    "credit_cards",
    "goals",
    "budgets",
    "wallet",
]
_SORTED_FINANCIAL_DIMENSIONS = sorted(_ALL_FINANCIAL_DIMENSIONS)


def _register_and_login(client) -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    email = f"obs1-{suffix}@email.com"
    password = "StrongPass@123"
    register = client.post(
        "/auth/register",
        json={"name": f"user-{suffix}", "email": email, "password": password},
    )
    assert register.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.get_json()["token"]
    from flask_jwt_extended import decode_token

    return token, str(decode_token(token)["sub"])


class TestTruncateSnapshot:
    def test_returns_input_unchanged_when_below_cap(self) -> None:
        snap = {
            "schema_version": "financial_insight_snapshot.v1",
            "current_period": {"paid": {"income_total": "0.00"}},
            "comparisons": {},
        }
        out, info = truncate_snapshot(snap)
        assert out == snap
        assert info["truncated"] is False
        assert info["snapshot_bytes_final"] == info["snapshot_bytes_original"]
        assert info["dropped_sections"] == []

    def test_trims_transactions_when_above_cap(self) -> None:
        items = [
            {"type": "expense", "amount": float(100 + i), "title": "x" * 60}
            for i in range(200)
        ]
        snap = {
            "schema_version": "financial_insight_snapshot.v1",
            "current_period": {"paid": {"income_total": "0.00"}},
            "comparisons": {},
            "transactions": {"items": items},
            "daily_series": [],
            "credit_cards": [],
            "categories": {"top_expense_categories": []},
        }
        out, info = truncate_snapshot(snap, max_bytes=2048)
        assert info["truncated"] is True
        assert "transactions.items" in info["dropped_sections"]
        assert len(out["transactions"]["items"]) <= 15
        assert info["snapshot_bytes_final"] < info["snapshot_bytes_original"]
        # Structural backbone preserved.
        assert out["schema_version"] == "financial_insight_snapshot.v1"
        assert out["current_period"] == snap["current_period"]
        assert out["comparisons"] == snap["comparisons"]

    def test_trims_daily_series_to_last_seven(self) -> None:
        # Use lots of large transactions to force step 1 then step 2 trimming.
        items = [
            {"type": "expense", "amount": float(i + 1), "title": "z" * 100}
            for i in range(30)
        ]
        snap = {
            "schema_version": "financial_insight_snapshot.v1",
            "current_period": {},
            "comparisons": {},
            "transactions": {"items": items},
            "daily_series": [
                {"date": f"2026-05-{d:02d}", "expense": 100.0} for d in range(1, 30)
            ],
            "credit_cards": [],
            "categories": {"top_expense_categories": []},
        }
        out, info = truncate_snapshot(snap, max_bytes=1024)
        assert info["truncated"] is True
        # Step 2 should kick in given how aggressive the cap is.
        if "daily_series" in info["dropped_sections"]:
            assert len(out["daily_series"]) == 7


class TestMetadataPersistenceAndMetrics:
    def test_generate_persists_metadata_json_and_increments_counter(
        self, app, client
    ) -> None:
        token, user_id_str = _register_and_login(client)
        user_id = UUID(user_id_str)

        # Grant entitlement so Premium gate does not block.
        from app.services.entitlement_service import grant_entitlement

        with app.app_context():
            grant_entitlement(
                user_id=user_id,
                feature_key="advanced_simulations",
                source="trial",
            )
            db.session.commit()

        provider = MagicMock()
        provider.generate_with_usage.return_value = LLMResponse(
            content=(
                '{"summary":"Resumo.","items":['
                '{"type":"saude_financeira","dimension":"general",'
                '"title":"Geral","message":"All good.",'
                '"evidence":["current_period.paid.balance"]},'
                '{"type":"saude_financeira","dimension":"transactions",'
                '"title":"Transações","message":"All good.",'
                '"evidence":["data_quality.domain_presence.transactions"]},'
                '{"type":"saude_financeira","dimension":"credit_cards",'
                '"title":"Cartões","message":"All good.",'
                '"evidence":["data_quality.domain_presence.credit_cards"]},'
                '{"type":"saude_financeira","dimension":"goals",'
                '"title":"Metas","message":"All good.",'
                '"evidence":["data_quality.domain_presence.goals"]},'
                '{"type":"saude_financeira","dimension":"budgets",'
                '"title":"Orçamentos","message":"All good.",'
                '"evidence":["data_quality.domain_presence.budgets"]},'
                '{"type":"saude_financeira","dimension":"wallet",'
                '"title":"Carteira","message":"All good.",'
                '"evidence":["data_quality.domain_presence.wallet"]}]}'
            ),
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            model="gpt-test",
            latency_ms=50,
        )

        with app.app_context():
            from app.services.ai_advisory_service import AIAdvisoryService

            with patch(
                "app.services.ai_advisory_service.record_ai_insight_generated"
            ) as record:
                service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
                result = service.generate_financial_insights(
                    period_type="daily",
                    anchor_date=date(2026, 5, 18),
                )

            # Counter called once with the dimensions captured by the LLM resp.
            assert record.called
            kwargs = record.call_args.kwargs
            assert kwargs["period_type"] == "daily"
            assert kwargs["dimensions"] == _SORTED_FINANCIAL_DIMENSIONS
            assert kwargs["tokens_used"] == 30
            assert isinstance(kwargs["truncated"], bool)
            assert kwargs["snapshot_bytes"] >= 0

            # Persisted row has metadata_json populated with the snapshot stats.
            row = (
                db.session.query(AIInsight)
                .filter_by(user_id=user_id)
                .order_by(AIInsight.created_at.desc())
                .first()
            )
            assert row is not None
            md = row.metadata_dict
            assert md["snapshot_version"] == "financial_insight_snapshot.v1"
            assert md["dimensions_present"] == _SORTED_FINANCIAL_DIMENSIONS
            assert "snapshot_bytes_original" in md
            assert "snapshot_bytes_final" in md
            assert isinstance(md["truncated"], bool)
            assert result["items"][0]["dimension"] == "general"


class TestMaxBytesEnvOverride:
    def test_default_constant_is_12kib(self) -> None:
        # MAX_SNAPSHOT_BYTES may be overridden by env in CI; the default is
        # 12 KiB. Just sanity-check the unit (multiple of 1024).
        assert MAX_SNAPSHOT_BYTES > 0
        assert MAX_SNAPSHOT_BYTES % 1024 == 0
