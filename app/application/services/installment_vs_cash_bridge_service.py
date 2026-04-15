from __future__ import annotations

import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Callable, cast
from uuid import UUID

from app.application.services.transaction_application_service import (
    TransactionApplicationService,
)
from app.models.simulation import Simulation
from app.services.goal_service import GoalService
from app.services.installment_vs_cash_types import (
    InstallmentVsCashGoalBridgeInput,
    InstallmentVsCashPlannedExpenseBridgeInput,
    SerializedGoal,
    SerializedTransaction,
)


class InstallmentVsCashBridgeService:
    def __init__(
        self,
        *,
        user_id: UUID,
        goal_service_factory: Callable[[UUID], GoalService],
        transaction_application_service_factory: Callable[
            [UUID], TransactionApplicationService
        ],
    ) -> None:
        self._goal_service = goal_service_factory(user_id)
        self._transaction_application_service = transaction_application_service_factory(
            user_id
        )

    @classmethod
    def with_defaults(cls, user_id: UUID) -> InstallmentVsCashBridgeService:
        return cls(
            user_id=user_id,
            goal_service_factory=GoalService,
            transaction_application_service_factory=TransactionApplicationService.with_defaults,
        )

    def create_goal(
        self,
        *,
        simulation: Simulation,
        payload: InstallmentVsCashGoalBridgeInput,
    ) -> SerializedGoal:
        selected_option = str(payload["selected_option"])
        option_total = _read_result_money(simulation, selected_option)
        goal = self._goal_service.create_goal(
            _compact_optional_fields(
                {
                    "title": payload["title"],
                    "description": payload.get("description"),
                    "category": payload.get("category"),
                    "target_amount": _money_str(option_total),
                    "current_amount": _money_str(
                        Decimal(str(payload.get("current_amount", "0.00")))
                    ),
                    "target_date": _date_to_iso(payload.get("target_date")),
                    "priority": payload.get("priority", 3),
                    "status": "active",
                }
            )
        )
        return cast(SerializedGoal, self._goal_service.serialize(goal))

    def create_planned_expense(
        self,
        *,
        simulation: Simulation,
        payload: InstallmentVsCashPlannedExpenseBridgeInput,
    ) -> list[SerializedTransaction]:
        selected_option = str(payload["selected_option"])
        if selected_option == "cash":
            return self._create_cash_expense(simulation=simulation, payload=payload)

        return self._create_installment_expense(
            simulation=simulation,
            payload=payload,
        )

    def _create_cash_expense(
        self,
        *,
        simulation: Simulation,
        payload: InstallmentVsCashPlannedExpenseBridgeInput,
    ) -> list[SerializedTransaction]:
        transaction_result = self._transaction_application_service.create_transaction(
            _compact_optional_fields(
                {
                    "title": payload["title"],
                    "description": payload.get("description"),
                    "observation": payload.get("observation"),
                    "amount": _money_str(_read_result_money(simulation, "cash")),
                    "currency": payload.get("currency", "BRL"),
                    "status": payload.get("status", "pending"),
                    "type": "expense",
                    "due_date": payload.get("due_date"),
                    "tag_id": payload.get("tag_id"),
                    "account_id": payload.get("account_id"),
                    "credit_card_id": payload.get("credit_card_id"),
                    "is_installment": False,
                }
            ),
            installment_amount_builder=_build_installment_amounts,
        )
        return cast(list[SerializedTransaction], transaction_result["items"])

    def _create_installment_expense(
        self,
        *,
        simulation: Simulation,
        payload: InstallmentVsCashPlannedExpenseBridgeInput,
    ) -> list[SerializedTransaction]:
        installment = simulation.result["options"]["installment"]
        created_items: list[SerializedTransaction] = []
        installment_result = self._transaction_application_service.create_transaction(
            _compact_optional_fields(
                {
                    "title": payload["title"],
                    "description": payload.get("description"),
                    "observation": payload.get("observation"),
                    "amount": installment["nominal_total"],
                    "currency": payload.get("currency", "BRL"),
                    "status": payload.get("status", "pending"),
                    "type": "expense",
                    "due_date": payload.get("first_due_date"),
                    "tag_id": payload.get("tag_id"),
                    "account_id": payload.get("account_id"),
                    "credit_card_id": payload.get("credit_card_id"),
                    "is_installment": True,
                    "installment_count": installment["count"],
                }
            ),
            installment_amount_builder=_build_installment_amounts,
        )
        created_items.extend(
            cast(list[SerializedTransaction], installment_result["items"])
        )

        upfront_fees = Decimal(str(installment["upfront_fees"]))
        if upfront_fees > Decimal("0.00"):
            fee_result = self._transaction_application_service.create_transaction(
                _compact_optional_fields(
                    {
                        "title": f"{payload['title']} - custos iniciais",
                        "description": payload.get("description"),
                        "observation": payload.get("observation"),
                        "amount": _money_str(upfront_fees),
                        "currency": payload.get("currency", "BRL"),
                        "status": payload.get("status", "pending"),
                        "type": "expense",
                        "due_date": payload.get("upfront_due_date")
                        or payload.get("first_due_date"),
                        "tag_id": payload.get("tag_id"),
                        "account_id": payload.get("account_id"),
                        "credit_card_id": payload.get("credit_card_id"),
                        "is_installment": False,
                    }
                ),
                installment_amount_builder=_build_installment_amounts,
            )
            created_items.extend(cast(list[SerializedTransaction], fee_result["items"]))

        return created_items


def _build_installment_amounts(total: Decimal, count: int) -> list[Decimal]:
    normalized_total = Decimal(str(total)).quantize(Decimal("0.01"))
    base_amount = (normalized_total / count).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )
    amounts = [base_amount] * count
    remainder = (normalized_total - (base_amount * count)).quantize(Decimal("0.01"))
    amounts[-1] = (amounts[-1] + remainder).quantize(Decimal("0.01"))
    return amounts


def _read_result_money(simulation: Simulation, selected_option: str) -> Decimal:
    comparison = simulation.result["comparison"]
    if selected_option == "cash":
        return Decimal(str(comparison["cash_option_total"]))
    return Decimal(str(comparison["installment_option_total"]))


def _money_str(value: Decimal) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.01")), ".2f")


def _compact_optional_fields(
    payload: dict[str, object | None],
) -> dict[str, object]:
    return {key: value for key, value in payload.items() if value is not None}


def _date_to_iso(value: object) -> str | None:
    """Convert a datetime.date to ISO string; downstream schemas expect strings."""
    if isinstance(value, datetime.date):
        return value.isoformat()
    return None
