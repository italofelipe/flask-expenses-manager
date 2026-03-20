from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.application.services.installment_vs_cash_bridge_service import (
    InstallmentVsCashBridgeService,
)


class _FakeGoalService:
    def __init__(self) -> None:
        self.created_payloads: list[dict[str, object]] = []

    def create_goal(self, payload: dict[str, object]) -> SimpleNamespace:
        self.created_payloads.append(payload)
        return SimpleNamespace(id=uuid4(), **payload)

    def serialize(self, goal: SimpleNamespace) -> dict[str, object]:
        return {
            "id": str(goal.id),
            "title": goal.title,
            "target_amount": goal.target_amount,
            "category": getattr(goal, "category", None),
        }


class _FakeTransactionApplicationService:
    def __init__(self) -> None:
        self.created_payloads: list[dict[str, object]] = []

    def create_transaction(
        self,
        payload: dict[str, object],
        *,
        installment_amount_builder,
    ) -> dict[str, object]:
        self.created_payloads.append(payload)
        amount = Decimal(str(payload["amount"]))
        items: list[dict[str, object]]
        if payload.get("is_installment"):
            count = int(payload["installment_count"])
            amounts = installment_amount_builder(amount, count)
            items = [
                {
                    "title": f"{payload['title']} ({index + 1}/{count})",
                    "amount": format(amounts[index], ".2f"),
                    "is_installment": True,
                }
                for index in range(count)
            ]
        else:
            items = [
                {
                    "title": str(payload["title"]),
                    "amount": format(amount, ".2f"),
                    "is_installment": False,
                }
            ]
        return {"items": items}


def _simulation(*, upfront_fees: str = "0.00") -> SimpleNamespace:
    return SimpleNamespace(
        result={
            "comparison": {
                "cash_option_total": "900.00",
                "installment_option_total": "1050.00",
            },
            "options": {
                "installment": {
                    "count": 3,
                    "nominal_total": "990.00",
                    "upfront_fees": upfront_fees,
                }
            },
        }
    )


def test_installment_vs_cash_bridge_service_creates_goal_from_selected_option() -> None:
    fake_goal_service = _FakeGoalService()
    service = InstallmentVsCashBridgeService(
        user_id=uuid4(),
        goal_service_factory=lambda _user_id: fake_goal_service,
        transaction_application_service_factory=(
            lambda _user_id: _FakeTransactionApplicationService()
        ),
    )

    result = service.create_goal(
        simulation=_simulation(),
        payload={
            "title": "Notebook novo",
            "selected_option": "cash",
            "category": "planned_purchase",
            "current_amount": "100.00",
        },
    )

    assert fake_goal_service.created_payloads[0]["target_amount"] == "900.00"
    assert result["title"] == "Notebook novo"
    assert result["target_amount"] == "900.00"


def test_installment_vs_cash_bridge_service_creates_installments_and_upfront_fee() -> (
    None
):
    fake_transaction_service = _FakeTransactionApplicationService()
    service = InstallmentVsCashBridgeService(
        user_id=uuid4(),
        goal_service_factory=lambda _user_id: _FakeGoalService(),
        transaction_application_service_factory=(
            lambda _user_id: fake_transaction_service
        ),
    )

    result = service.create_planned_expense(
        simulation=_simulation(upfront_fees="60.00"),
        payload={
            "title": "Notebook novo",
            "selected_option": "installment",
            "first_due_date": "2026-04-15",
            "status": "pending",
            "currency": "BRL",
        },
    )

    assert len(fake_transaction_service.created_payloads) == 2
    assert fake_transaction_service.created_payloads[0]["is_installment"] is True
    assert fake_transaction_service.created_payloads[1]["title"] == (
        "Notebook novo - custos iniciais"
    )
    assert len(result) == 4
