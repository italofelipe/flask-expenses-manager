from __future__ import annotations

from flask import Response, request
from flask_apispec.views import MethodResource

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.auth import current_user_id
from app.controllers.response_contract import (
    compat_error_response,
    compat_success_response,
)
from app.controllers.transaction.dependencies import get_transaction_dependencies
from app.controllers.transaction.utils import _guard_revoked_token
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required


class DashboardOverviewResource(MethodResource):
    @doc(
        description=(
            "Contrato canônico do dashboard financeiro do MVP1. "
            "Use esta rota para visão agregada mensal; "
            "`/transactions/dashboard` permanece apenas como compatibilidade "
            "transitória."
        ),
        tags=["Dashboard"],
        security=[{"BearerAuth": []}],
        params={
            "month": {
                "description": "Mês de referência no formato YYYY-MM",
                "in": "query",
                "type": "string",
                "required": True,
            },
            "X-API-Contract": {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
        },
        responses={
            200: {"description": "Overview do dashboard"},
            400: {"description": "Parâmetro inválido"},
            401: {"description": "Token inválido"},
            500: {"description": "Erro interno"},
        },
    )
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        dependencies = get_transaction_dependencies()
        query_service = dependencies.transaction_query_service_factory(user_uuid)

        try:
            result = query_service.get_dashboard_overview(
                month=str(request.args.get("month", ""))
            )
        except TransactionApplicationError as exc:
            return compat_error_response(
                legacy_payload={"error": exc.message, "details": exc.details},
                status_code=exc.status_code,
                message=exc.message,
                error_code=exc.code,
                details=exc.details,
            )
        except Exception:
            return compat_error_response(
                legacy_payload={"error": "Erro ao calcular overview do dashboard"},
                status_code=500,
                message="Erro ao calcular overview do dashboard",
                error_code="INTERNAL_ERROR",
            )

        return compat_success_response(
            legacy_payload={
                "month": result["month"],
                "income_total": result["income_total"],
                "expense_total": result["expense_total"],
                "balance": result["balance"],
                "counts": result["counts"],
                "top_expense_categories": result["top_expense_categories"],
                "top_income_categories": result["top_income_categories"],
            },
            status_code=200,
            message="Overview do dashboard calculado com sucesso",
            data={
                "month": result["month"],
                "totals": {
                    "income_total": result["income_total"],
                    "expense_total": result["expense_total"],
                    "balance": result["balance"],
                },
                "counts": result["counts"],
                "top_categories": {
                    "expense": result["top_expense_categories"],
                    "income": result["top_income_categories"],
                },
            },
        )


__all__ = ["DashboardOverviewResource"]
