"""Tests for MVP-3 extensions in the FinancialInsightContextBuilder + AI service.

Covers the new pieces required by the MVP-3 wiki:
- `credit_cards` section in snapshot (reuses bill cycle + utilization service)
- Extended comparisons in daily snapshot (`previous_week`, `same_day_previous_year`)
- `dimension` field on each LLM item, validated against the closed enum
- Legacy AIInsight rows without `dimension` coerced to `general`
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.extensions.database import db
from app.models.credit_card import CreditCard
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.ai_advisory_service import (
    _FINANCIAL_INSIGHT_RESPONSE_SCHEMA,
    _coerce_financial_insight_item,
)
from app.services.financial_insight_context_builder import (
    INSIGHT_DIMENSIONS,
    FinancialInsightContextBuilder,
)
from app.services.llm_provider import LLMProviderError


def _create_user(client) -> str:
    suffix = uuid4().hex[:8]
    email = f"mvp3-{suffix}@email.com"
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

    return str(decode_token(token)["sub"])


def _create_card(app, *, user_id: str, limit_amount: float = 5000.0) -> str:
    with app.app_context():
        card = CreditCard(
            user_id=UUID(user_id),
            name="Nubank",
            brand="mastercard",
            limit_amount=Decimal(str(limit_amount)),
            closing_day=10,
            due_day=15,
        )
        db.session.add(card)
        db.session.commit()
        return str(card.id)


def _add_card_charge(
    app,
    *,
    user_id: str,
    card_id: str,
    amount: str,
    due_date: date,
    status: TransactionStatus = TransactionStatus.PENDING,
) -> None:
    with app.app_context():
        tx = Transaction(
            user_id=UUID(user_id),
            credit_card_id=UUID(card_id),
            title="charge",
            amount=Decimal(amount),
            due_date=due_date,
            status=status,
            type=TransactionType.EXPENSE,
        )
        db.session.add(tx)
        db.session.commit()


class TestCreditCardsSnapshotSection:
    def test_daily_snapshot_includes_credit_cards_section(self, app, client):
        user_id = _create_user(client)
        card_id = _create_card(app, user_id=user_id, limit_amount=2000.0)
        _add_card_charge(
            app,
            user_id=user_id,
            card_id=card_id,
            amount="500.00",
            due_date=date.today(),
        )

        with app.app_context():
            snapshot = FinancialInsightContextBuilder().build_daily(
                user_id=UUID(user_id),
                anchor_date=date.today(),
            )

        assert "credit_cards" in snapshot
        assert isinstance(snapshot["credit_cards"], list)
        assert len(snapshot["credit_cards"]) == 1
        entry = snapshot["credit_cards"][0]
        # Sensitive PII like raw user_id or full card token must NOT appear.
        assert "user_id" not in entry
        assert "limit_amount" in entry
        assert "utilization_pct" in entry
        assert "cycle" in entry
        assert entry["cycle"]["start_date"]
        assert entry["cycle"]["end_date"]

    def test_user_without_cards_returns_empty_list(self, app, client):
        user_id = _create_user(client)
        with app.app_context():
            snapshot = FinancialInsightContextBuilder().build_daily(
                user_id=UUID(user_id),
                anchor_date=date.today(),
            )
        assert snapshot["credit_cards"] == []

    def test_monthly_snapshot_also_includes_credit_cards(self, app, client):
        user_id = _create_user(client)
        _create_card(app, user_id=user_id)
        with app.app_context():
            snapshot = FinancialInsightContextBuilder().build_monthly(
                user_id=UUID(user_id),
                anchor_date=date(2026, 5, 17),
            )
        assert isinstance(snapshot.get("credit_cards"), list)
        assert len(snapshot["credit_cards"]) == 1


class TestExtendedComparisons:
    def test_daily_snapshot_emits_same_day_previous_year_when_omitting(
        self, app, client
    ):
        """When there's no data 1 year ago, the comparison is omitted but flagged."""
        user_id = _create_user(client)
        with app.app_context():
            snapshot = FinancialInsightContextBuilder().build_daily(
                user_id=UUID(user_id),
                anchor_date=date.today(),
            )
        comparisons = snapshot["comparisons"]
        missing = snapshot["data_quality"]["missing_comparison_periods"]
        # If there is no prior-year data, key MAY be absent; assert flag instead.
        if "same_day_previous_year" not in comparisons:
            assert "same_day_previous_year" in missing

    def test_daily_snapshot_emits_previous_week_comparison(self, app, client):
        user_id = _create_user(client)
        with app.app_context():
            snapshot = FinancialInsightContextBuilder().build_daily(
                user_id=UUID(user_id),
                anchor_date=date.today(),
            )
        comparisons = snapshot["comparisons"]
        assert "previous_week" in comparisons or (
            "previous_week" in snapshot["data_quality"]["missing_comparison_periods"]
        )


class TestInsightDimensions:
    def test_dimension_enum_has_canonical_values(self):
        assert set(INSIGHT_DIMENSIONS) == {
            "general",
            "transactions",
            "credit_cards",
            "goals",
            "budgets",
            "wallet",
        }

    def test_llm_response_schema_requires_dimension_on_items(self):
        item_schema = _FINANCIAL_INSIGHT_RESPONSE_SCHEMA["schema"]["properties"][
            "items"
        ]["items"]
        assert "dimension" in item_schema["properties"]
        assert "dimension" in item_schema["required"]
        assert set(item_schema["properties"]["dimension"]["enum"]) == set(
            INSIGHT_DIMENSIONS
        )

    def test_coerce_accepts_valid_dimension(self):
        coerced = _coerce_financial_insight_item(
            {
                "type": "padrao_gasto",
                "title": "Cartão Nubank no limite",
                "message": "Você usou 80% do limite este ciclo.",
                "evidence": ["snap.credit_cards[0].utilization_pct"],
                "dimension": "credit_cards",
            }
        )
        assert coerced["dimension"] == "credit_cards"

    def test_coerce_rejects_invalid_dimension(self):
        with pytest.raises(LLMProviderError):
            _coerce_financial_insight_item(
                {
                    "type": "padrao_gasto",
                    "title": "x",
                    "message": "y",
                    "evidence": ["z"],
                    "dimension": "investments",  # not in enum
                }
            )

    def test_coerce_legacy_item_defaults_to_general(self):
        """Items persisted before MVP-3 have no dimension — default to 'general'."""
        coerced = _coerce_financial_insight_item(
            {
                "type": "padrao_gasto",
                "title": "Despesas estáveis",
                "message": "Padrão semelhante ao mês anterior.",
                "evidence": ["snap.current_period.paid.expense_total"],
            }
        )
        assert coerced["dimension"] == "general"
