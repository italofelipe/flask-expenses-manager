"""Tests for the financial snapshot builder used by AI insights (#1269)."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from app.extensions.database import db
from app.models.budget import Budget
from app.models.goal import Goal
from app.models.transaction import (
    Transaction,
    TransactionCategory,
    TransactionStatus,
    TransactionType,
)
from app.models.user import User
from app.services.financial_insight_context_builder import (
    FinancialInsightContextBuilder,
)


def _make_user() -> uuid.UUID:
    user = User(
        name="Ana Cliente",
        email=f"ana-{uuid.uuid4().hex[:8]}@example.com",
        password="hashed",
    )
    db.session.add(user)
    db.session.commit()
    return user.id


def _make_transaction(
    user_id: uuid.UUID,
    *,
    title: str,
    amount: str,
    tx_type: TransactionType,
    status: TransactionStatus,
    due_date: date,
    category: TransactionCategory | None = None,
    description: str | None = None,
    observation: str | None = None,
    external_id: str | None = None,
    bank_name: str | None = None,
) -> Transaction:
    tx = Transaction(
        user_id=user_id,
        title=title,
        description=description if description is not None else title,
        observation=observation,
        external_id=external_id,
        bank_name=bank_name,
        amount=Decimal(amount),
        type=tx_type,
        status=status,
        due_date=due_date,
        category=category,
    )
    db.session.add(tx)
    db.session.commit()
    db.session.refresh(tx)
    return tx


def _make_budget(
    user_id: uuid.UUID,
    *,
    name: str,
    amount: str,
    category: TransactionCategory | None = None,
) -> Budget:
    budget = Budget(
        user_id=user_id,
        name=name,
        amount=Decimal(amount),
        period="monthly",
        category=category.value if category else None,
        is_active=True,
    )
    db.session.add(budget)
    db.session.commit()
    return budget


def _make_goal(
    user_id: uuid.UUID,
    *,
    title: str,
    current_amount: str,
    target_amount: str,
    target_date: date | None = None,
) -> Goal:
    goal = Goal(
        user_id=user_id,
        title=title,
        current_amount=Decimal(current_amount),
        target_amount=Decimal(target_amount),
        target_date=target_date,
        status="active",
    )
    db.session.add(goal)
    db.session.commit()
    return goal


def _as_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class TestFinancialInsightContextBuilderDaily:
    def test_daily_snapshot_compares_today_yesterday_previous_month_and_mtd(
        self, app
    ) -> None:
        with app.app_context():
            user_id = _make_user()
            anchor = date(2026, 5, 17)
            _make_transaction(
                user_id,
                title="Salário",
                amount="1000.00",
                tx_type=TransactionType.INCOME,
                status=TransactionStatus.PAID,
                due_date=anchor,
            )
            _make_transaction(
                user_id,
                title="Mercado",
                amount="250.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=anchor,
                category=TransactionCategory.alimentacao,
            )
            _make_transaction(
                user_id,
                title="Conta pendente",
                amount="80.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PENDING,
                due_date=anchor,
            )
            _make_transaction(
                user_id,
                title="Conta vencida",
                amount="33.25",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.OVERDUE,
                due_date=anchor,
            )
            _make_transaction(
                user_id,
                title="Despesa cancelada",
                amount="999.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.CANCELLED,
                due_date=anchor,
            )
            _make_transaction(
                user_id,
                title="Ontem mercado",
                amount="400.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 16),
            )
            _make_transaction(
                user_id,
                title="Dia mês passado",
                amount="100.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 4, 17),
            )
            _make_transaction(
                user_id,
                title="Receita mês passado",
                amount="500.00",
                tx_type=TransactionType.INCOME,
                status=TransactionStatus.PAID,
                due_date=date(2026, 4, 17),
            )
            _make_transaction(
                user_id,
                title="Gasto do mês",
                amount="50.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 1),
            )
            _make_transaction(
                user_id,
                title="Receita do mês",
                amount="234.00",
                tx_type=TransactionType.INCOME,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 1),
            )

            snapshot = FinancialInsightContextBuilder().build_daily(
                user_id=user_id,
                anchor_date=anchor,
            )

        assert snapshot["schema_version"] == "financial_insight_snapshot.v1"
        assert snapshot["period_type"] == "daily"
        assert snapshot["period"] == {
            "start": "2026-05-17",
            "end": "2026-05-17",
            "label": "2026-05-17",
        }
        assert snapshot["current_period"]["paid"] == {
            "income_total": "1000.00",
            "expense_total": "250.00",
            "balance": "750.00",
            "transaction_count": 2,
        }
        assert snapshot["current_period"]["commitments"]["pending_expense_total"] == (
            "80.00"
        )
        assert snapshot["current_period"]["commitments"]["overdue_expense_total"] == (
            "33.25"
        )
        assert snapshot["current_period"]["commitments"]["transaction_count"] == 2
        assert snapshot["current_period"]["cancelled_transaction_count"] == 1
        assert snapshot["comparisons"]["yesterday"]["paid"]["expense_total"] == (
            "400.00"
        )
        assert snapshot["comparisons"]["yesterday"]["delta"]["expense_total"] == (
            "-150.00"
        )
        assert (
            snapshot["comparisons"]["same_day_previous_month"]["paid"]["income_total"]
            == "500.00"
        )
        assert (
            snapshot["comparisons"]["same_day_previous_month"]["delta"]["income_total"]
            == "500.00"
        )
        assert (
            snapshot["comparisons"]["month_to_date"]["paid"]["expense_total"]
            == "700.00"
        )

    def test_daily_snapshot_marks_missing_previous_month_same_day(self, app) -> None:
        with app.app_context():
            user_id = _make_user()
            anchor = date(2026, 3, 31)
            _make_transaction(
                user_id,
                title="Receita do dia",
                amount="100.00",
                tx_type=TransactionType.INCOME,
                status=TransactionStatus.PAID,
                due_date=anchor,
            )

            snapshot = FinancialInsightContextBuilder().build_daily(
                user_id=user_id,
                anchor_date=anchor,
            )

        assert "same_day_previous_month" not in snapshot["comparisons"]
        assert snapshot["data_quality"]["missing_comparison_periods"] == [
            "same_day_previous_month"
        ]

    def test_snapshot_redacts_user_pii_and_sensitive_transaction_fields(
        self, app
    ) -> None:
        with app.app_context():
            user_id = _make_user()
            _make_transaction(
                user_id,
                title="Consulta CPF 123.456.789-00",
                description="Enviar recibo para ana@example.com",
                observation="Observação privada com telefone 11999998888",
                external_id="bank-secret-123",
                bank_name="Banco Sensível",
                amount="70.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 17),
            )

            snapshot = FinancialInsightContextBuilder().build_daily(
                user_id=user_id,
                anchor_date=date(2026, 5, 17),
            )

        serialized = _as_json(snapshot)
        assert "Ana Cliente" not in serialized
        assert "ana@example.com" not in serialized
        assert "123.456.789-00" not in serialized
        assert "11999998888" not in serialized
        assert "bank-secret-123" not in serialized
        assert "Banco Sensível" not in serialized
        assert "observation" not in serialized
        assert "external_id" not in serialized
        assert "bank_name" not in serialized
        assert snapshot["transactions"]["sample"][0]["title"] == "Consulta CPF [cpf]"


class TestFinancialInsightContextBuilderWeekly:
    def test_weekly_snapshot_summarizes_day_extremes_and_previous_week(
        self, app
    ) -> None:
        with app.app_context():
            user_id = _make_user()
            anchor = date(2026, 5, 13)  # Wednesday, ISO week starts 2026-05-11
            _make_transaction(
                user_id,
                title="Segunda gasto",
                amount="100.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 11),
                category=TransactionCategory.transporte,
            )
            _make_transaction(
                user_id,
                title="Segunda receita",
                amount="10.00",
                tx_type=TransactionType.INCOME,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 11),
            )
            _make_transaction(
                user_id,
                title="Terça gasto",
                amount="500.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 12),
                category=TransactionCategory.alimentacao,
            )
            _make_transaction(
                user_id,
                title="Quarta receita",
                amount="1000.00",
                tx_type=TransactionType.INCOME,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 13),
            )
            _make_transaction(
                user_id,
                title="Domingo gasto",
                amount="50.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 17),
                category=TransactionCategory.lazer,
            )
            _make_transaction(
                user_id,
                title="Semana anterior",
                amount="200.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 5),
            )

            snapshot = FinancialInsightContextBuilder().build_weekly(
                user_id=user_id,
                anchor_date=anchor,
            )

        assert snapshot["period_type"] == "weekly"
        assert snapshot["period"]["start"] == "2026-05-11"
        assert snapshot["period"]["end"] == "2026-05-17"
        assert len(snapshot["daily_series"]) == 7
        assert snapshot["current_period"]["paid"]["expense_total"] == "650.00"
        assert (
            snapshot["comparisons"]["previous_period"]["paid"]["expense_total"]
            == "200.00"
        )
        assert snapshot["extremes"]["max_expense_day"] == {
            "date": "2026-05-12",
            "amount": "500.00",
        }
        assert snapshot["extremes"]["min_expense_day_with_activity"] == {
            "date": "2026-05-17",
            "amount": "50.00",
        }
        assert snapshot["extremes"]["max_income_day"] == {
            "date": "2026-05-13",
            "amount": "1000.00",
        }
        assert snapshot["extremes"]["min_income_day_with_activity"] == {
            "date": "2026-05-11",
            "amount": "10.00",
        }
        assert snapshot["categories"]["top_expense_categories"][0] == {
            "category": "alimentacao",
            "total": "500.00",
        }


class TestFinancialInsightContextBuilderMonthly:
    def test_monthly_snapshot_includes_day_extremes_budgets_and_goals(
        self, app
    ) -> None:
        with app.app_context():
            user_id = _make_user()
            anchor = date(2026, 5, 17)
            _make_transaction(
                user_id,
                title="Maior gasto",
                amount="1000.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 2),
                category=TransactionCategory.alimentacao,
            )
            _make_transaction(
                user_id,
                title="Menor gasto",
                amount="100.00",
                tx_type=TransactionType.EXPENSE,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 7),
                category=TransactionCategory.transporte,
            )
            _make_transaction(
                user_id,
                title="Maior receita",
                amount="2000.00",
                tx_type=TransactionType.INCOME,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 20),
            )
            _make_transaction(
                user_id,
                title="Menor receita",
                amount="300.00",
                tx_type=TransactionType.INCOME,
                status=TransactionStatus.PAID,
                due_date=date(2026, 5, 3),
            )
            _make_budget(
                user_id,
                name="Alimentação",
                amount="800.00",
                category=TransactionCategory.alimentacao,
            )
            _make_goal(
                user_id,
                title="Comprar carro",
                current_amount="1200.00",
                target_amount="5000.00",
                target_date=date(2026, 12, 31),
            )

            snapshot = FinancialInsightContextBuilder().build_monthly(
                user_id=user_id,
                anchor_date=anchor,
            )

        assert snapshot["period_type"] == "monthly"
        assert snapshot["period"]["start"] == "2026-05-01"
        assert snapshot["period"]["end"] == "2026-05-31"
        assert len(snapshot["daily_series"]) == 31
        assert snapshot["current_period"]["paid"] == {
            "income_total": "2300.00",
            "expense_total": "1100.00",
            "balance": "1200.00",
            "transaction_count": 4,
        }
        assert snapshot["extremes"]["max_expense_day"] == {
            "date": "2026-05-02",
            "amount": "1000.00",
        }
        assert snapshot["extremes"]["min_expense_day_with_activity"] == {
            "date": "2026-05-07",
            "amount": "100.00",
        }
        assert snapshot["extremes"]["max_income_day"] == {
            "date": "2026-05-20",
            "amount": "2000.00",
        }
        assert snapshot["extremes"]["min_income_day_with_activity"] == {
            "date": "2026-05-03",
            "amount": "300.00",
        }
        assert snapshot["budgets"] == [
            {
                "name": "Alimentação",
                "category": "alimentacao",
                "period": "monthly",
                "amount": "800.00",
                "spent": "1000.00",
                "utilization_pct": "125.00",
                "exceeded": True,
            }
        ]
        assert snapshot["goals"] == [
            {
                "title": "Comprar carro",
                "current_amount": "1200.00",
                "target_amount": "5000.00",
                "progress_pct": "24.00",
                "target_date": "2026-12-31",
            }
        ]
