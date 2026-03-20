from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any, Callable
from uuid import UUID

from flask import current_app
from marshmallow import ValidationError

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
    TransactionApplicationService,
)
from app.extensions.database import db
from app.models.simulation import Simulation
from app.schemas.installment_vs_cash_schema import (
    InstallmentVsCashCalculationSchema,
    InstallmentVsCashGoalBridgeSchema,
    InstallmentVsCashPlannedExpenseBridgeSchema,
    InstallmentVsCashSaveSchema,
)
from app.services.goal_service import GoalService, GoalServiceError
from app.services.installment_vs_cash_service import InstallmentVsCashService
from app.services.simulation_service import SimulationService, SimulationServiceError


@dataclass(frozen=True)
class InstallmentVsCashApplicationError(Exception):
    message: str
    code: str
    status_code: int
    details: dict[str, Any] | None = None


class InstallmentVsCashApplicationService:
    def __init__(
        self,
        *,
        user_id: UUID | None,
        calculator_factory: Callable[[], InstallmentVsCashService],
        simulation_service_factory: Callable[[UUID], SimulationService],
        goal_service_factory: Callable[[UUID], GoalService],
        transaction_application_service_factory: Callable[
            [UUID], TransactionApplicationService
        ],
    ) -> None:
        self._user_id = user_id
        self._calculator = calculator_factory()
        self._simulation_service_factory = simulation_service_factory
        self._goal_service_factory = goal_service_factory
        self._transaction_application_service_factory = (
            transaction_application_service_factory
        )
        self._calculation_schema = InstallmentVsCashCalculationSchema()
        self._save_schema = InstallmentVsCashSaveSchema()
        self._goal_bridge_schema = InstallmentVsCashGoalBridgeSchema()
        self._expense_bridge_schema = InstallmentVsCashPlannedExpenseBridgeSchema()

    @classmethod
    def with_defaults(
        cls,
        user_id: UUID | None,
    ) -> InstallmentVsCashApplicationService:
        default_rate = Decimal(
            str(
                current_app.config.get(
                    "INSTALLMENT_VS_CASH_DEFAULT_OPPORTUNITY_RATE_ANNUAL",
                    "12.00",
                )
            )
        )
        return cls(
            user_id=user_id,
            calculator_factory=lambda: InstallmentVsCashService(
                default_opportunity_rate_annual_percent=default_rate
            ),
            simulation_service_factory=SimulationService,
            goal_service_factory=GoalService,
            transaction_application_service_factory=TransactionApplicationService.with_defaults,
        )

    def calculate(self, payload: dict[str, Any]) -> dict[str, Any]:
        validated = self._load_schema(self._calculation_schema, payload)
        try:
            calculation = self._calculator.calculate(validated)
        except ValueError as exc:
            raise InstallmentVsCashApplicationError(
                message=str(exc),
                code="VALIDATION_ERROR",
                status_code=400,
            ) from exc
        return self._serialize_calculation(calculation)

    def save_simulation(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = self._require_authenticated_user()
        validated = self._load_schema(self._save_schema, payload)
        try:
            calculation = self._calculator.calculate(validated)
        except ValueError as exc:
            raise InstallmentVsCashApplicationError(
                message=str(exc),
                code="VALIDATION_ERROR",
                status_code=400,
            ) from exc
        simulation_service = self._simulation_service_factory(user_id)
        try:
            simulation = simulation_service.save_simulation(
                {
                    "tool_id": calculation.tool_id,
                    "rule_version": calculation.rule_version,
                    "inputs": calculation.inputs,
                    "result": calculation.result,
                }
            )
        except SimulationServiceError as exc:
            raise _to_application_error(exc) from exc
        return {
            "simulation": simulation_service.serialize(simulation),
            "calculation": self._serialize_calculation(calculation),
        }

    def create_goal_from_simulation(
        self,
        simulation_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        user_id = self._require_authenticated_user()
        validated = self._load_schema(self._goal_bridge_schema, payload)
        simulation_service = self._simulation_service_factory(user_id)
        goal_service = self._goal_service_factory(user_id)
        simulation = self._load_installment_vs_cash_simulation(
            simulation_service=simulation_service,
            simulation_id=simulation_id,
        )
        selected_option = str(validated["selected_option"])
        option_total = _read_result_money(simulation, selected_option)
        goal_payload = _compact_optional_fields(
            {
                "title": validated["title"],
                "description": validated.get("description"),
                "category": validated.get("category"),
                "target_amount": _money_str(option_total),
                "current_amount": _money_str(
                    Decimal(str(validated.get("current_amount", "0.00")))
                ),
                "target_date": validated.get("target_date"),
                "priority": validated.get("priority", 3),
                "status": "active",
            }
        )
        try:
            goal = goal_service.create_goal(goal_payload)
        except GoalServiceError as exc:
            raise _to_application_error(exc) from exc

        simulation.goal_id = goal.id
        db.session.commit()
        return {
            "goal": goal_service.serialize(goal),
            "simulation": simulation_service.serialize(simulation),
        }

    def create_planned_expense_from_simulation(
        self,
        simulation_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        user_id = self._require_authenticated_user()
        validated = self._load_schema(self._expense_bridge_schema, payload)
        simulation_service = self._simulation_service_factory(user_id)
        transaction_service = self._transaction_application_service_factory(user_id)
        simulation = self._load_installment_vs_cash_simulation(
            simulation_service=simulation_service,
            simulation_id=simulation_id,
        )
        selected_option = str(validated["selected_option"])

        try:
            if selected_option == "cash":
                transaction_result = transaction_service.create_transaction(
                    {
                        "title": validated["title"],
                        "description": validated.get("description"),
                        "observation": validated.get("observation"),
                        "amount": _money_str(_read_result_money(simulation, "cash")),
                        "currency": validated.get("currency", "BRL"),
                        "status": validated.get("status", "pending"),
                        "type": "expense",
                        "due_date": validated["due_date"],
                        "tag_id": validated.get("tag_id"),
                        "account_id": validated.get("account_id"),
                        "credit_card_id": validated.get("credit_card_id"),
                        "is_installment": False,
                    },
                    installment_amount_builder=_build_installment_amounts,
                )
                created_items = transaction_result["items"]
            else:
                installment = simulation.result["options"]["installment"]
                created_items = []
                installment_result = transaction_service.create_transaction(
                    {
                        "title": validated["title"],
                        "description": validated.get("description"),
                        "observation": validated.get("observation"),
                        "amount": installment["nominal_total"],
                        "currency": validated.get("currency", "BRL"),
                        "status": validated.get("status", "pending"),
                        "type": "expense",
                        "due_date": validated["first_due_date"],
                        "tag_id": validated.get("tag_id"),
                        "account_id": validated.get("account_id"),
                        "credit_card_id": validated.get("credit_card_id"),
                        "is_installment": True,
                        "installment_count": installment["count"],
                    },
                    installment_amount_builder=_build_installment_amounts,
                )
                created_items.extend(installment_result["items"])
                upfront_fees = Decimal(str(installment["upfront_fees"]))
                if upfront_fees > Decimal("0.00"):
                    fee_result = transaction_service.create_transaction(
                        {
                            "title": f"{validated['title']} - custos iniciais",
                            "description": validated.get("description"),
                            "observation": validated.get("observation"),
                            "amount": _money_str(upfront_fees),
                            "currency": validated.get("currency", "BRL"),
                            "status": validated.get("status", "pending"),
                            "type": "expense",
                            "due_date": validated.get("upfront_due_date")
                            or validated["first_due_date"],
                            "tag_id": validated.get("tag_id"),
                            "account_id": validated.get("account_id"),
                            "credit_card_id": validated.get("credit_card_id"),
                            "is_installment": False,
                        },
                        installment_amount_builder=_build_installment_amounts,
                    )
                    created_items.extend(fee_result["items"])
        except TransactionApplicationError as exc:
            raise _to_application_error(exc) from exc

        return {
            "transactions": created_items,
            "simulation": simulation_service.serialize(simulation),
        }

    def _load_schema(self, schema: Any, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return schema.load(payload)
        except ValidationError as exc:
            raise InstallmentVsCashApplicationError(
                message="Dados inválidos para a simulação parcelado vs à vista.",
                code="VALIDATION_ERROR",
                status_code=400,
                details={"messages": exc.messages},
            ) from exc

    def _require_authenticated_user(self) -> UUID:
        if self._user_id is None:
            raise InstallmentVsCashApplicationError(
                message="Autenticação obrigatória para esta operação.",
                code="UNAUTHORIZED",
                status_code=401,
            )
        return self._user_id

    def _load_installment_vs_cash_simulation(
        self,
        *,
        simulation_service: SimulationService,
        simulation_id: UUID,
    ) -> Simulation:
        try:
            simulation = simulation_service.get_simulation(simulation_id)
        except SimulationServiceError as exc:
            raise _to_application_error(exc) from exc
        if simulation.tool_id != InstallmentVsCashService.TOOL_ID:
            raise InstallmentVsCashApplicationError(
                message=(
                    "A simulação informada não pertence à ferramenta "
                    "parcelado vs à vista."
                ),
                code="INVALID_SIMULATION_TOOL",
                status_code=400,
            )
        return simulation

    def _serialize_calculation(self, calculation: Any) -> dict[str, Any]:
        return {
            "tool_id": calculation.tool_id,
            "rule_version": calculation.rule_version,
            "input": calculation.inputs,
            "result": calculation.result,
        }


def _to_application_error(exc: Any) -> InstallmentVsCashApplicationError:
    return InstallmentVsCashApplicationError(
        message=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        details=getattr(exc, "details", None),
    )


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


def _compact_optional_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
