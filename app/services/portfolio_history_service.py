from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from app.application.errors import PublicValidationError
from app.models.investment_operation import InvestmentOperation
from app.models.wallet import Wallet
from app.services.investment_service import InvestmentService

FIXED_INCOME_ASSET_CLASSES = {"cdb", "cdi", "lci", "lca", "tesouro"}


@dataclass
class PortfolioHistoryRange:
    start_date: date
    end_date: date


@dataclass
class WalletState:
    wallet: Wallet
    has_operations: bool
    quantity: Decimal
    cost_basis: Decimal
    operations_by_date: dict[date, list[InvestmentOperation]]


class PortfolioHistoryService:
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    def get_history(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> dict[str, Any]:
        history_range = self._resolve_range(start_date=start_date, end_date=end_date)
        wallets = cast(list[Wallet], Wallet.query.filter_by(user_id=self.user_id).all())
        ticker_prices = self._load_ticker_prices(wallets, history_range)
        opening_invested = self._build_opening_events(wallets, history_range.start_date)
        events = self._build_events(history_range=history_range, wallets=wallets)
        if opening_invested > 0:
            opening_event = self._ensure_day_event(events, history_range.start_date)
            opening_event["buy_amount"] += opening_invested
            opening_event["buy_operations"] += 1
            opening_event["total_operations"] += 1

        states = self._build_wallet_states(wallets, history_range.start_date)
        items = self._build_daily_series(
            history_range=history_range,
            events=events,
            states=states,
            ticker_prices=ticker_prices,
        )

        total_buy_amount = sum((Decimal(i["buy_amount"]) for i in items), Decimal("0"))
        total_sell_amount = sum(
            (Decimal(i["sell_amount"]) for i in items), Decimal("0")
        )
        total_net = sum(
            (Decimal(i["net_invested_amount"]) for i in items), Decimal("0")
        )
        final_cumulative = (
            Decimal(items[-1]["cumulative_net_invested"]) if items else Decimal("0")
        )
        final_current_value = (
            Decimal(items[-1]["total_current_value_estimate"])
            if items
            else Decimal("0")
        )

        return {
            "summary": {
                "start_date": history_range.start_date.isoformat(),
                "end_date": history_range.end_date.isoformat(),
                "total_points": len(items),
                "total_buy_amount": str(total_buy_amount),
                "total_sell_amount": str(total_sell_amount),
                "total_net_invested_amount": str(total_net),
                "final_cumulative_net_invested": str(final_cumulative),
                "final_total_current_value_estimate": str(final_current_value),
                "final_total_profit_loss_estimate": str(
                    final_current_value - final_cumulative
                ),
            },
            "items": items,
        }

    def _resolve_range(
        self, *, start_date: date | None, end_date: date | None
    ) -> PortfolioHistoryRange:
        today = date.today()
        resolved_end = end_date or today
        resolved_start = start_date or (resolved_end - timedelta(days=30))
        if resolved_start > resolved_end:
            raise PublicValidationError("startDate não pode ser maior que finalDate.")
        return PortfolioHistoryRange(start_date=resolved_start, end_date=resolved_end)

    def _load_ticker_prices(
        self, wallets: list[Wallet], history_range: PortfolioHistoryRange
    ) -> dict[str, dict[str, float]]:
        prices: dict[str, dict[str, float]] = {}
        for wallet in wallets:
            if not wallet.ticker:
                continue
            ticker = wallet.ticker.upper()
            if ticker in prices:
                continue
            prices[ticker] = InvestmentService.get_historical_prices(
                ticker,
                start_date=history_range.start_date.isoformat(),
                end_date=history_range.end_date.isoformat(),
            )
        return prices

    def _build_opening_events(self, wallets: list[Wallet], start_date: date) -> Decimal:
        opening_invested = Decimal("0")
        for wallet in wallets:
            if wallet.operations:
                _, cost_basis = self._compute_position_until(
                    wallet.operations, before_date=start_date
                )
                if cost_basis > 0:
                    opening_invested += cost_basis
                continue
            if wallet.register_date < start_date:
                opening_invested += self._wallet_base_amount(wallet)
        return opening_invested

    def _build_events(
        self, *, history_range: PortfolioHistoryRange, wallets: list[Wallet]
    ) -> dict[date, dict[str, Any]]:
        events: dict[date, dict[str, Any]] = {}

        for wallet in wallets:
            if wallet.operations:
                self._append_operation_events(
                    events=events,
                    operations=wallet.operations,
                    history_range=history_range,
                )
                continue

            self._append_wallet_registration_event(
                events=events,
                wallet=wallet,
                history_range=history_range,
            )

        return events

    @staticmethod
    def _is_date_within_range(
        event_date: date, history_range: PortfolioHistoryRange
    ) -> bool:
        return history_range.start_date <= event_date <= history_range.end_date

    def _append_operation_events(
        self,
        *,
        events: dict[date, dict[str, Any]],
        operations: list[InvestmentOperation],
        history_range: PortfolioHistoryRange,
    ) -> None:
        for operation in operations:
            operation_date = operation.executed_at
            if not self._is_date_within_range(operation_date, history_range):
                continue

            day_event = self._ensure_day_event(events, operation_date)
            quantity = Decimal(str(operation.quantity))
            unit_price = Decimal(str(operation.unit_price))
            fees = Decimal(str(operation.fees or 0))
            if operation.operation_type == "buy":
                amount = (quantity * unit_price) + fees
                day_event["buy_amount"] += amount
                day_event["buy_operations"] += 1
            else:
                amount = (quantity * unit_price) - fees
                day_event["sell_amount"] += amount
                day_event["sell_operations"] += 1
            day_event["total_operations"] += 1

    def _append_wallet_registration_event(
        self,
        *,
        events: dict[date, dict[str, Any]],
        wallet: Wallet,
        history_range: PortfolioHistoryRange,
    ) -> None:
        register_date = wallet.register_date
        if not self._is_date_within_range(register_date, history_range):
            return
        base_amount = self._wallet_base_amount(wallet)
        if base_amount <= 0:
            return
        day_event = self._ensure_day_event(events, register_date)
        day_event["buy_amount"] += base_amount
        day_event["buy_operations"] += 1
        day_event["total_operations"] += 1

    def _build_wallet_states(
        self, wallets: list[Wallet], start_date: date
    ) -> list[WalletState]:
        states: list[WalletState] = []
        for wallet in wallets:
            if wallet.operations:
                quantity, cost_basis = self._compute_position_until(
                    wallet.operations, before_date=start_date
                )
                operations_by_date: dict[date, list[InvestmentOperation]] = {}
                for operation in wallet.operations:
                    if operation.executed_at < start_date:
                        continue
                    operations_by_date.setdefault(operation.executed_at, []).append(
                        operation
                    )
                states.append(
                    WalletState(
                        wallet=wallet,
                        has_operations=True,
                        quantity=quantity,
                        cost_basis=cost_basis,
                        operations_by_date=operations_by_date,
                    )
                )
                continue
            base_quantity = (
                Decimal(str(wallet.quantity))
                if wallet.quantity is not None
                else Decimal("1")
            )
            states.append(
                WalletState(
                    wallet=wallet,
                    has_operations=False,
                    quantity=base_quantity,
                    cost_basis=self._wallet_base_amount(wallet),
                    operations_by_date={},
                )
            )
        return states

    @staticmethod
    def _compute_position_until(
        operations: list[InvestmentOperation], *, before_date: date
    ) -> tuple[Decimal, Decimal]:
        quantity = Decimal("0")
        cost_basis = Decimal("0")
        ordered_ops = sorted(
            operations,
            key=lambda op: (op.executed_at, op.created_at or op.executed_at),
        )
        for operation in ordered_ops:
            if operation.executed_at >= before_date:
                continue
            op_quantity = Decimal(str(operation.quantity))
            op_price = Decimal(str(operation.unit_price))
            op_fees = Decimal(str(operation.fees or 0))
            if operation.operation_type == "buy":
                quantity += op_quantity
                cost_basis += (op_quantity * op_price) + op_fees
                continue
            if quantity <= 0:
                continue
            reduce_qty = min(op_quantity, quantity)
            average_cost = cost_basis / quantity if quantity > 0 else Decimal("0")
            cost_basis -= average_cost * reduce_qty
            quantity -= op_quantity
            if quantity <= 0:
                quantity = Decimal("0")
                cost_basis = Decimal("0")
        return quantity, cost_basis

    @staticmethod
    def _wallet_base_amount(wallet: Wallet) -> Decimal:
        quantity = (
            Decimal(str(wallet.quantity)) if wallet.quantity is not None else None
        )
        if wallet.value is not None and quantity is not None:
            return Decimal(str(wallet.value)) * quantity
        if wallet.value is not None:
            return Decimal(str(wallet.value))
        if wallet.estimated_value_on_create_date is not None:
            return Decimal(str(wallet.estimated_value_on_create_date))
        return Decimal("0")

    @staticmethod
    def _ensure_day_event(
        events: dict[date, dict[str, Any]], event_date: date
    ) -> dict[str, Any]:
        if event_date not in events:
            events[event_date] = {
                "buy_amount": Decimal("0"),
                "sell_amount": Decimal("0"),
                "total_operations": 0,
                "buy_operations": 0,
                "sell_operations": 0,
            }
        return events[event_date]

    def _build_daily_series(
        self,
        *,
        history_range: PortfolioHistoryRange,
        events: dict[date, dict[str, Any]],
        states: list[WalletState],
        ticker_prices: dict[str, dict[str, float]],
    ) -> list[dict[str, Any]]:
        current_date = history_range.start_date
        cumulative_net = Decimal("0")
        items: list[dict[str, Any]] = []

        while current_date <= history_range.end_date:
            for state in states:
                for operation in state.operations_by_date.get(current_date, []):
                    self._apply_operation(state, operation)

            event = events.get(
                current_date,
                {
                    "buy_amount": Decimal("0"),
                    "sell_amount": Decimal("0"),
                    "total_operations": 0,
                    "buy_operations": 0,
                    "sell_operations": 0,
                },
            )
            net = event["buy_amount"] - event["sell_amount"]
            cumulative_net += net
            current_value = self._estimate_current_value(
                day=current_date,
                states=states,
                ticker_prices=ticker_prices,
            )
            profit_loss = current_value - cumulative_net
            items.append(
                {
                    "date": current_date.isoformat(),
                    "total_operations": event["total_operations"],
                    "buy_operations": event["buy_operations"],
                    "sell_operations": event["sell_operations"],
                    "buy_amount": str(event["buy_amount"]),
                    "sell_amount": str(event["sell_amount"]),
                    "net_invested_amount": str(net),
                    "cumulative_net_invested": str(cumulative_net),
                    "total_current_value_estimate": str(current_value),
                    "total_profit_loss_estimate": str(profit_loss),
                }
            )
            current_date += timedelta(days=1)
        return items

    @staticmethod
    def _apply_operation(state: WalletState, operation: InvestmentOperation) -> None:
        quantity = Decimal(str(operation.quantity))
        unit_price = Decimal(str(operation.unit_price))
        fees = Decimal(str(operation.fees or 0))
        if operation.operation_type == "buy":
            state.quantity += quantity
            state.cost_basis += (quantity * unit_price) + fees
            return
        if state.quantity <= 0:
            return
        reduce_qty = min(quantity, state.quantity)
        average_cost = state.cost_basis / state.quantity
        state.cost_basis -= average_cost * reduce_qty
        state.quantity -= quantity
        if state.quantity <= 0:
            state.quantity = Decimal("0")
            state.cost_basis = Decimal("0")

    def _estimate_current_value(
        self,
        *,
        day: date,
        states: list[WalletState],
        ticker_prices: dict[str, dict[str, float]],
    ) -> Decimal:
        total = Decimal("0")
        for state in states:
            wallet = state.wallet
            asset_class = str(wallet.asset_class or "custom").lower()
            if wallet.ticker:
                ticker = wallet.ticker.upper()
                price = ticker_prices.get(ticker, {}).get(day.isoformat())
                if price is not None:
                    total += Decimal(str(price)) * state.quantity
                    continue
            if (
                asset_class in FIXED_INCOME_ASSET_CLASSES
                and wallet.annual_rate is not None
            ):
                annual_rate = Decimal(str(wallet.annual_rate)) / Decimal("100")
                growth_days = max((day - wallet.register_date).days, 0)
                growth_factor = (Decimal("1") + annual_rate) ** (
                    Decimal(growth_days) / Decimal("365")
                )
                invested_base = (
                    state.cost_basis
                    if state.cost_basis > 0
                    else self._wallet_base_amount(wallet)
                )
                total += invested_base * growth_factor
                continue
            total += (
                state.cost_basis
                if state.cost_basis > 0
                else self._wallet_base_amount(wallet)
            )
        return total
