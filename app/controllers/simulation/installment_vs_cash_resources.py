from __future__ import annotations

from uuid import UUID

from flask.typing import ResponseReturnValue
from flask_apispec.views import MethodResource

from app.application.services.installment_vs_cash_application_service import (
    InstallmentVsCashApplicationError,
)
from app.auth import current_user_id
from app.schemas.installment_vs_cash_schema import (
    InstallmentVsCashCalculationSchema,
    InstallmentVsCashGoalBridgeSchema,
    InstallmentVsCashPlannedExpenseBridgeSchema,
    InstallmentVsCashSaveSchema,
)
from app.services.entitlement_service import require_entitlement
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_success, installment_vs_cash_application_error_response
from .dependencies import get_simulation_dependencies


class InstallmentVsCashCalculationResource(MethodResource):
    @doc(
        description=(
            "Executa a simulação pública de parcelado vs à vista, retornando "
            "comparativo, cronograma e recomendação."
        ),
        tags=["Simulações"],
        security=[],
        responses={
            200: {"description": "Simulação calculada com sucesso"},
            400: {"description": "Dados inválidos"},
        },
    )
    @use_kwargs(InstallmentVsCashCalculationSchema, location="json")
    def post(self, **kwargs: object) -> ResponseReturnValue:
        dependencies = get_simulation_dependencies()
        service = dependencies.installment_vs_cash_application_service_factory(None)
        try:
            result = service.calculate(dict(kwargs))
        except InstallmentVsCashApplicationError as exc:
            return installment_vs_cash_application_error_response(exc)

        return compat_success(
            legacy_payload=result,
            status_code=200,
            message="Simulação calculada com sucesso",
            data=result,
        )


class InstallmentVsCashSaveResource(MethodResource):
    @doc(
        description="Recalcula e persiste uma simulação parcelado vs à vista.",
        tags=["Simulações"],
        security=[{"BearerAuth": []}],
        responses={
            201: {"description": "Simulação salva com sucesso"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido"},
        },
    )
    @jwt_required()
    @use_kwargs(InstallmentVsCashSaveSchema, location="json")
    def post(self, **kwargs: object) -> ResponseReturnValue:
        dependencies = get_simulation_dependencies()
        service = dependencies.installment_vs_cash_application_service_factory(
            current_user_id()
        )
        try:
            result = service.save_simulation(dict(kwargs))
        except InstallmentVsCashApplicationError as exc:
            return installment_vs_cash_application_error_response(exc)

        return compat_success(
            legacy_payload={
                "message": "Simulação salva com sucesso",
                "simulation": result["simulation"],
            },
            status_code=201,
            message="Simulação salva com sucesso",
            data=result,
        )


class SimulationGoalBridgeResource(MethodResource):
    @doc(
        description="Converte uma simulação salva em meta de compra.",
        tags=["Simulações"],
        security=[{"BearerAuth": []}],
        responses={
            201: {"description": "Meta criada a partir da simulação"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido"},
            403: {"description": "Entitlement necessário"},
            404: {"description": "Simulação não encontrada"},
        },
    )
    @jwt_required()
    @require_entitlement("advanced_simulations")
    @use_kwargs(InstallmentVsCashGoalBridgeSchema, location="json")
    def post(self, simulation_id: UUID, **kwargs: object) -> ResponseReturnValue:
        dependencies = get_simulation_dependencies()
        service = dependencies.installment_vs_cash_application_service_factory(
            current_user_id()
        )
        try:
            result = service.create_goal_from_simulation(simulation_id, dict(kwargs))
        except InstallmentVsCashApplicationError as exc:
            return installment_vs_cash_application_error_response(exc)

        return compat_success(
            legacy_payload={
                "message": "Meta criada com sucesso a partir da simulação",
                "goal": result["goal"],
                "simulation": result["simulation"],
            },
            status_code=201,
            message="Meta criada com sucesso a partir da simulação",
            data=result,
        )


class SimulationPlannedExpenseBridgeResource(MethodResource):
    @doc(
        description="Converte uma simulação salva em despesa planejada.",
        tags=["Simulações"],
        security=[{"BearerAuth": []}],
        responses={
            201: {"description": "Despesa planejada criada a partir da simulação"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido"},
            403: {"description": "Entitlement necessário"},
            404: {"description": "Simulação não encontrada"},
        },
    )
    @jwt_required()
    @require_entitlement("advanced_simulations")
    @use_kwargs(InstallmentVsCashPlannedExpenseBridgeSchema, location="json")
    def post(self, simulation_id: UUID, **kwargs: object) -> ResponseReturnValue:
        dependencies = get_simulation_dependencies()
        service = dependencies.installment_vs_cash_application_service_factory(
            current_user_id()
        )
        try:
            result = service.create_planned_expense_from_simulation(
                simulation_id,
                dict(kwargs),
            )
        except InstallmentVsCashApplicationError as exc:
            return installment_vs_cash_application_error_response(exc)

        return compat_success(
            legacy_payload={
                "message": "Despesa planejada criada com sucesso a partir da simulação",
                "transactions": result["transactions"],
                "simulation": result["simulation"],
            },
            status_code=201,
            message="Despesa planejada criada com sucesso a partir da simulação",
            data=result,
        )
