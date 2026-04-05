from __future__ import annotations

import re

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
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)
from app.services.cache_service import DASHBOARD_CACHE_TTL, get_cache_service
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

# Month query-param must match YYYY-MM exactly; reject anything else to prevent
# log-injection attacks (Sonar S5145 / CWE-117).
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


class DashboardOverviewResource(MethodResource):
    @doc(
        summary="Obter overview mensal do dashboard",
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
                "example": "2026-03",
            },
            **contract_header_param(supported_version="v2"),
        },
        responses={
            200: json_success_response(
                description="Overview do dashboard",
                message="Overview do dashboard calculado com sucesso",
                data_example={
                    "month": "2026-03",
                    "totals": {
                        "income_total": 5000.0,
                        "expense_total": 3200.0,
                        "balance": 1800.0,
                    },
                    "counts": {
                        "total_transactions": 14,
                        "income_transactions": 4,
                        "expense_transactions": 10,
                        "status": {"paid": 9, "pending": 5},
                    },
                    "top_categories": {
                        "expense": [
                            {
                                "tag_id": "73c3b094-60bf-45d5-8e32-0f673b2ab4a2",
                                "category_name": "Moradia",
                                "total_amount": 1800.0,
                                "transactions_count": 3,
                            }
                        ],
                        "income": [
                            {
                                "tag_id": None,
                                "category_name": "Receitas",
                                "total_amount": 5000.0,
                                "transactions_count": 4,
                            }
                        ],
                    },
                },
            ),
            400: json_error_response(
                description="Parâmetro inválido",
                message="Parâmetro 'month' inválido. Use o formato YYYY-MM.",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Token inválido",
                message="Token revogado",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            500: json_error_response(
                description="Erro interno",
                message="Erro ao calcular overview do dashboard",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        month_raw = str(request.args.get("month", ""))
        # Sanitise: only allow YYYY-MM to prevent log-injection (S5145)
        month = month_raw if _MONTH_RE.match(month_raw) else ""
        cache = get_cache_service()
        cache_key = f"dashboard:overview:{user_uuid}:{month}"

        cached = cache.get(cache_key)
        if cached is not None:
            resp = compat_success_response(
                legacy_payload=cached["legacy"],
                status_code=200,
                message="Overview do dashboard calculado com sucesso",
                data=cached["data"],
            )
            resp.headers["X-Cache"] = "HIT"
            return resp

        dependencies = get_transaction_dependencies()
        query_service = dependencies.transaction_query_service_factory(user_uuid)

        try:
            result = query_service.get_dashboard_overview(month=month)
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

        legacy = {
            "month": result["month"],
            "income_total": result["income_total"],
            "expense_total": result["expense_total"],
            "balance": result["balance"],
            "counts": result["counts"],
            "top_expense_categories": result["top_expense_categories"],
            "top_income_categories": result["top_income_categories"],
        }
        data = {
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
        }
        cache.set(cache_key, {"legacy": legacy, "data": data}, ttl=DASHBOARD_CACHE_TTL)
        resp = compat_success_response(
            legacy_payload=legacy,
            status_code=200,
            message="Overview do dashboard calculado com sucesso",
            data=data,
        )
        resp.headers["X-Cache"] = "MISS"
        return resp


__all__ = ["DashboardOverviewResource"]
