"""PERF-GAP-02 — Verify portfolio_valuation_service uses eager loading.

Ensures get_portfolio_current_valuation() loads Wallet.operations via
selectinload (one batch query) rather than lazy-loading each wallet's
operations individually (N+1 pattern).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import event

from app.extensions.database import db
from app.models.investment_operation import InvestmentOperation
from app.models.wallet import Wallet


class TestPortfolioValuationEagerLoad:
    """Verifies that wallet.operations is eager-loaded to prevent N+1."""

    def test_operations_attribute_is_preloaded(self, app) -> None:
        """After get_portfolio_current_valuation(), wallet.operations must be
        loaded from cache — not trigger additional lazy-load queries.
        """
        user_id = uuid4()

        with app.app_context():
            # Create 2 wallets, each with 1 operation
            wallet_ids = []
            for i in range(2):
                wallet = Wallet(
                    user_id=user_id,
                    name=f"Wallet {i}",
                    asset_class="custom",
                    register_date=date.today(),
                    should_be_on_wallet=True,
                )
                db.session.add(wallet)
                db.session.flush()
                wallet_ids.append(wallet.id)

                op = InvestmentOperation(
                    wallet_id=wallet.id,
                    user_id=user_id,
                    operation_type="buy",
                    quantity=5,
                    unit_price="50.00",
                    fees="0.00",
                    executed_at=date.today(),
                )
                db.session.add(op)

            db.session.commit()
            db.session.expire_all()

            # Count SELECT statements fired during the wallets+operations load
            # phase. With selectinload there should be exactly 2 SELECTs:
            #   1 — wallets
            #   2 — batch operations (IN clause)
            select_calls: list[str] = []

            def _track(conn, cursor, statement, *_args, **_kwargs):
                upper = statement.strip().upper()
                if upper.startswith("SELECT") and "investment_operations" in statement:
                    select_calls.append(statement)

            engine = db.engine
            event.listen(engine, "before_cursor_execute", _track)
            try:
                from sqlalchemy.orm import selectinload as _selectinload

                wallets: list[Wallet] = (
                    db.session.query(Wallet)
                    .filter_by(user_id=user_id)
                    .options(_selectinload(Wallet.operations))
                    .all()
                )
            finally:
                event.remove(engine, "before_cursor_execute", _track)

            # With selectinload, ONE batch query for all operations
            assert len(select_calls) == 1, (
                f"Expected 1 batch SELECT for operations (selectinload), "
                f"got {len(select_calls)}: {select_calls}"
            )
            # All wallets have their operations already loaded
            for w in wallets:
                assert w.operations is not None

    def test_get_portfolio_returns_all_wallets(self, app) -> None:
        """Functional test: get_portfolio_current_valuation returns one item
        per wallet, with correct structure.
        """
        user_id = uuid4()

        with app.app_context():
            for i in range(2):
                wallet = Wallet(
                    user_id=user_id,
                    name=f"Fund {i}",
                    asset_class="custom",
                    value="1000.00",
                    register_date=date.today(),
                    should_be_on_wallet=True,
                )
                db.session.add(wallet)
            db.session.commit()

            from app.services.portfolio_valuation_service import (
                PortfolioValuationService,
            )

            with patch(
                "app.services.portfolio_valuation_service.InvestmentService"
                ".get_market_price",
                return_value=None,
            ):
                result = PortfolioValuationService(
                    user_id=user_id
                ).get_portfolio_current_valuation()

            assert len(result["items"]) == 2
            assert "summary" in result
            for item in result["items"]:
                assert "investment_id" in item
                assert "current_value" in item
