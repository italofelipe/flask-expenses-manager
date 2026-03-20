from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, TypeAlias, cast
from uuid import UUID

from flask import current_app
from marshmallow import Schema, ValidationError

from app.application.services.installment_vs_cash_bridge_service import (
    InstallmentVsCashBridgeService,
)
from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.extensions.database import db
from app.models.simulation import Simulation
from app.schemas.installment_vs_cash_schema import (
    InstallmentVsCashCalculationSchema,
    InstallmentVsCashGoalBridgeSchema,
    InstallmentVsCashPlannedExpenseBridgeSchema,
    InstallmentVsCashSaveSchema,
)
from app.services.goal_service import GoalServiceError
from app.services.installment_vs_cash_service import InstallmentVsCashService
from app.services.installment_vs_cash_types import (
    InstallmentVsCashCalculation,
    InstallmentVsCashCalculationInput,
    InstallmentVsCashCalculationResponse,
    InstallmentVsCashGoalBridgeInput,
    InstallmentVsCashGoalBridgeResponse,
    InstallmentVsCashPlannedExpenseBridgeInput,
    InstallmentVsCashPlannedExpenseBridgeResponse,
    InstallmentVsCashSaveInput,
    InstallmentVsCashSaveResponse,
    SerializedSimulation,
)
from app.services.simulation_service import SimulationService, SimulationServiceError


@dataclass(frozen=True)
class InstallmentVsCashApplicationError(Exception):
    message: str
    code: str
    status_code: int
    details: dict[str, object] | None = None


class InstallmentVsCashApplicationService:
    def __init__(
        self,
        *,
        user_id: UUID | None,
        calculator_factory: _CalculatorFactory,
        simulation_service_factory: _SimulationServiceFactory,
        bridge_service_factory: _BridgeServiceFactory,
    ) -> None:
        self._user_id = user_id
        self._calculator = calculator_factory()
        self._simulation_service_factory = simulation_service_factory
        self._bridge_service_factory = bridge_service_factory
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
            bridge_service_factory=InstallmentVsCashBridgeService.with_defaults,
        )

    def calculate(
        self,
        payload: dict[str, object],
    ) -> InstallmentVsCashCalculationResponse:
        validated = self._load_calculation_payload(payload)
        calculation = self._calculate_or_error(validated)
        return self._serialize_calculation(calculation)

    def save_simulation(
        self,
        payload: dict[str, object],
    ) -> InstallmentVsCashSaveResponse:
        user_id = self._require_authenticated_user()
        validated = self._load_save_payload(payload)
        calculation = self._calculate_or_error(validated)
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
            "simulation": cast(
                SerializedSimulation,
                simulation_service.serialize(simulation),
            ),
            "calculation": self._serialize_calculation(calculation),
        }

    def create_goal_from_simulation(
        self,
        simulation_id: UUID,
        payload: dict[str, object],
    ) -> InstallmentVsCashGoalBridgeResponse:
        user_id = self._require_authenticated_user()
        validated = self._load_goal_bridge_payload(payload)
        simulation_service = self._simulation_service_factory(user_id)
        bridge_service = self._bridge_service_factory(user_id)
        simulation = self._load_installment_vs_cash_simulation(
            simulation_service=simulation_service,
            simulation_id=simulation_id,
        )
        try:
            goal = bridge_service.create_goal(
                simulation=simulation,
                payload=validated,
            )
        except GoalServiceError as exc:
            raise _to_application_error(exc) from exc

        simulation.goal_id = UUID(str(goal["id"]))
        db.session.commit()
        return {
            "goal": goal,
            "simulation": cast(
                SerializedSimulation,
                simulation_service.serialize(simulation),
            ),
        }

    def create_planned_expense_from_simulation(
        self,
        simulation_id: UUID,
        payload: dict[str, object],
    ) -> InstallmentVsCashPlannedExpenseBridgeResponse:
        user_id = self._require_authenticated_user()
        validated = self._load_expense_bridge_payload(payload)
        simulation_service = self._simulation_service_factory(user_id)
        bridge_service = self._bridge_service_factory(user_id)
        simulation = self._load_installment_vs_cash_simulation(
            simulation_service=simulation_service,
            simulation_id=simulation_id,
        )

        try:
            created_items = bridge_service.create_planned_expense(
                simulation=simulation,
                payload=validated,
            )
        except TransactionApplicationError as exc:
            raise _to_application_error(exc) from exc

        return {
            "transactions": created_items,
            "simulation": cast(
                SerializedSimulation,
                simulation_service.serialize(simulation),
            ),
        }

    def _load_calculation_payload(
        self,
        payload: dict[str, object],
    ) -> InstallmentVsCashCalculationInput:
        return cast(
            InstallmentVsCashCalculationInput,
            self._load_schema(self._calculation_schema, payload),
        )

    def _load_save_payload(
        self,
        payload: dict[str, object],
    ) -> InstallmentVsCashSaveInput:
        return cast(
            InstallmentVsCashSaveInput,
            self._load_schema(self._save_schema, payload),
        )

    def _load_goal_bridge_payload(
        self,
        payload: dict[str, object],
    ) -> InstallmentVsCashGoalBridgeInput:
        return cast(
            InstallmentVsCashGoalBridgeInput,
            self._load_schema(self._goal_bridge_schema, payload),
        )

    def _load_expense_bridge_payload(
        self,
        payload: dict[str, object],
    ) -> InstallmentVsCashPlannedExpenseBridgeInput:
        return cast(
            InstallmentVsCashPlannedExpenseBridgeInput,
            self._load_schema(self._expense_bridge_schema, payload),
        )

    def _load_schema(
        self,
        schema: Schema,
        payload: dict[str, object],
    ) -> dict[str, object]:
        try:
            return cast(dict[str, object], schema.load(payload))
        except ValidationError as exc:
            raise InstallmentVsCashApplicationError(
                message="Dados inválidos para a simulação parcelado vs à vista.",
                code="VALIDATION_ERROR",
                status_code=400,
                details={"messages": exc.messages},
            ) from exc

    def _calculate_or_error(
        self,
        payload: InstallmentVsCashCalculationInput,
    ) -> InstallmentVsCashCalculation:
        try:
            return self._calculator.calculate(payload)
        except ValueError as exc:
            raise InstallmentVsCashApplicationError(
                message=str(exc),
                code="VALIDATION_ERROR",
                status_code=400,
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

    def _serialize_calculation(
        self,
        calculation: InstallmentVsCashCalculation,
    ) -> InstallmentVsCashCalculationResponse:
        return {
            "tool_id": calculation.tool_id,
            "rule_version": calculation.rule_version,
            "input": calculation.inputs,
            "result": calculation.result,
        }


_CalculatorFactory: TypeAlias = Callable[[], InstallmentVsCashService]
_SimulationServiceFactory: TypeAlias = Callable[[UUID], SimulationService]
_BridgeServiceFactory: TypeAlias = Callable[[UUID], InstallmentVsCashBridgeService]
_ApplicationErrorSource: TypeAlias = (
    SimulationServiceError | GoalServiceError | TransactionApplicationError
)


def _to_application_error(
    exc: _ApplicationErrorSource,
) -> InstallmentVsCashApplicationError:
    return InstallmentVsCashApplicationError(
        message=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        details=getattr(exc, "details", None),
    )
