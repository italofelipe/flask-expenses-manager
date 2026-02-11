from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from graphql import GraphQLError

from app.extensions.database import db
from app.graphql import schema_utils
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.models.wallet import Wallet


def _create_user(*, name: str, email: str) -> User:
    user = User(name=name, email=email, password="hash")
    db.session.add(user)
    db.session.commit()
    return user


def test_parse_and_pagination_helpers() -> None:
    assert schema_utils._to_float_or_none(Decimal("10.50")) == 10.5
    assert schema_utils._to_float_or_none(None) is None

    assert schema_utils._parse_optional_date("2026-02-11", "start_date") == date(
        2026, 2, 11
    )
    assert schema_utils._parse_optional_date(None, "start_date") is None
    with pytest.raises(GraphQLError):
        schema_utils._parse_optional_date("11/02/2026", "start_date")

    assert schema_utils._parse_month("2026-02") == (2026, 2)
    with pytest.raises(GraphQLError):
        schema_utils._parse_month("2026-13")

    schema_utils._validate_pagination_values(1, 10)
    with pytest.raises(GraphQLError):
        schema_utils._validate_pagination_values(0, 10)
    with pytest.raises(GraphQLError):
        schema_utils._validate_pagination_values(1, 200)


def test_user_and_wallet_payload_serialization(app) -> None:
    with app.app_context():
        user = _create_user(name="user-graphql", email="user-graphql@email.com")
        user.monthly_income = Decimal("1234.56")
        user.birth_date = date(1990, 1, 2)
        db.session.commit()

        wallet_manual = Wallet(
            user_id=user.id,
            name="Reserva",
            value=Decimal("1000"),
            ticker=None,
            quantity=None,
            asset_class="custom",
            annual_rate=None,
            register_date=date(2026, 2, 11),
            should_be_on_wallet=True,
        )
        wallet_ticker = Wallet(
            user_id=user.id,
            name="Ação",
            value=None,
            ticker="PETR4",
            quantity=3,
            estimated_value_on_create_date=Decimal("75"),
            asset_class="stock",
            annual_rate=None,
            register_date=date(2026, 2, 11),
            should_be_on_wallet=True,
        )
        db.session.add_all([wallet_manual, wallet_ticker])
        db.session.commit()

        user_payload = schema_utils._user_to_graphql_payload(user)
        assert user_payload["id"] == str(user.id)
        assert user_payload["monthly_income"] == 1234.56
        assert user_payload["birth_date"] == "1990-01-02"

        basic_payload = schema_utils._user_basic_auth_payload(user)
        assert basic_payload == {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
        }

        manual_payload = schema_utils._wallet_to_graphql_payload(wallet_manual)
        assert manual_payload["value"] == 1000.0
        assert "ticker" not in manual_payload
        assert "estimated_value_on_create_date" not in manual_payload

        ticker_payload = schema_utils._wallet_to_graphql_payload(wallet_ticker)
        assert ticker_payload["ticker"] == "PETR4"
        assert ticker_payload["estimated_value_on_create_date"] == 75.0
        assert "value" not in ticker_payload


def test_query_filters_and_wallet_ownership_helpers(app) -> None:
    with app.app_context():
        owner = _create_user(name="owner", email="owner@email.com")
        other_user = _create_user(name="other", email="other@email.com")
        wallet = Wallet(
            user_id=owner.id,
            name="Carteira Owner",
            value=Decimal("500"),
            ticker=None,
            quantity=None,
            asset_class="custom",
            annual_rate=None,
            register_date=date(2026, 2, 11),
            should_be_on_wallet=True,
        )
        tx_income = Transaction(
            user_id=owner.id,
            title="Salário",
            amount=Decimal("1000"),
            type=TransactionType.INCOME,
            status=TransactionStatus.PAID,
            due_date=date(2026, 2, 10),
            currency="BRL",
        )
        tx_expense = Transaction(
            user_id=owner.id,
            title="Conta",
            amount=Decimal("200"),
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PENDING,
            due_date=date(2026, 2, 11),
            currency="BRL",
        )
        db.session.add_all([wallet, tx_income, tx_expense])
        db.session.commit()

        query = Transaction.query.filter_by(user_id=owner.id)
        query = schema_utils._apply_type_filter(query, "expense")
        assert query.count() == 1

        query = Transaction.query.filter_by(user_id=owner.id)
        query = schema_utils._apply_status_filter(query, "paid")
        assert query.count() == 1

        query = Transaction.query.filter_by(user_id=owner.id)
        ranged = schema_utils._apply_due_date_range_filter(
            query, "2026-02-10", "2026-02-11"
        )
        assert ranged.count() == 2

        with pytest.raises(GraphQLError):
            schema_utils._apply_type_filter(query, "invalid-type")
        with pytest.raises(GraphQLError):
            schema_utils._apply_status_filter(query, "invalid-status")
        with pytest.raises(GraphQLError):
            schema_utils._apply_due_date_range_filter(query, "2026-02-20", "2026-02-10")

        owned_wallet = schema_utils._get_owned_wallet_or_error(
            wallet.id,
            owner.id,
            forbidden_message="forbidden",
        )
        assert owned_wallet.id == wallet.id

        with pytest.raises(GraphQLError):
            schema_utils._get_owned_wallet_or_error(
                wallet.id,
                other_user.id,
                forbidden_message="forbidden",
            )

        with pytest.raises(GraphQLError):
            schema_utils._get_owned_wallet_or_error(
                investment_id=uuid4(),
                user_id=other_user.id,
                forbidden_message="forbidden",
            )

        with pytest.raises(GraphQLError):
            schema_utils._assert_owned_investment_access(wallet.id, other_user.id)

        schema_utils._assert_owned_investment_access(wallet.id, owner.id)
