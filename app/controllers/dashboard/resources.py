from __future__ import annotations

import re
from datetime import date
from typing import Any

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
from app.schemas.openapi.dashboard.docs import (
    DASHBOARD_OVERVIEW_DOC,
    DASHBOARD_SURVIVAL_DOC,
    DASHBOARD_TRENDS_DOC,
    DASHBOARD_WEEKLY_SUMMARY_DOC,
)
from app.services.cache_service import DASHBOARD_CACHE_TTL, get_cache_service
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

# Month query-param must match YYYY-MM exactly; reject anything else to prevent
# log-injection attacks (Sonar S5145 / CWE-117).
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VALID_PERIODS = {"1m", "3m", "6m"}


class DashboardOverviewResource(MethodResource):
    @doc(**DASHBOARD_OVERVIEW_DOC)
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


class DashboardTrendsResource(MethodResource):
    @doc(**DASHBOARD_TRENDS_DOC)
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        months_raw = request.args.get("months", "6")
        try:
            months = int(months_raw)
        except (ValueError, TypeError):
            months = -1

        if not (1 <= months <= 24):
            return compat_error_response(
                legacy_payload={
                    "error": "O parâmetro 'months' deve ser um inteiro entre 1 e 24."
                },
                status_code=422,
                message="O parâmetro 'months' deve ser um inteiro entre 1 e 24.",
                error_code="VALIDATION_ERROR",
            )

        user_uuid = current_user_id()
        cache = get_cache_service()
        cache_key = f"dashboard:trends:{user_uuid}:{months}"

        cached = cache.get(cache_key)
        if cached is not None:
            resp = compat_success_response(
                legacy_payload=cached,
                status_code=200,
                message="Tendências calculadas com sucesso",
                data=cached,
            )
            resp.headers["X-Cache"] = "HIT"
            return resp

        dependencies = get_transaction_dependencies()
        query_service = dependencies.transaction_query_service_factory(user_uuid)

        try:
            result = query_service.get_dashboard_trends(months=months)
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
                legacy_payload={"error": "Erro ao calcular tendências do dashboard"},
                status_code=500,
                message="Erro ao calcular tendências do dashboard",
                error_code="INTERNAL_ERROR",
            )

        result_dict: dict[str, Any] = dict(result)
        cache.set(cache_key, result_dict, ttl=DASHBOARD_CACHE_TTL)
        resp = compat_success_response(
            legacy_payload=result_dict,
            status_code=200,
            message="Tendências calculadas com sucesso",
            data=result_dict,
        )
        resp.headers["X-Cache"] = "MISS"
        return resp


class DashboardSurvivalIndexResource(MethodResource):
    @doc(**DASHBOARD_SURVIVAL_DOC)
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        cache = get_cache_service()
        cache_key = f"dashboard:survival-index:{user_uuid}"

        cached = cache.get(cache_key)
        if cached is not None:
            resp = compat_success_response(
                legacy_payload=cached,
                status_code=200,
                message="Índice de sobrevivência calculado com sucesso",
                data=cached,
            )
            resp.headers["X-Cache"] = "HIT"
            return resp

        dependencies = get_transaction_dependencies()
        query_service = dependencies.transaction_query_service_factory(user_uuid)

        try:
            result = query_service.get_survival_index()
        except Exception:
            return compat_error_response(
                legacy_payload={"error": "Erro ao calcular índice de sobrevivência"},
                status_code=500,
                message="Erro ao calcular índice de sobrevivência",
                error_code="INTERNAL_ERROR",
            )

        payload: dict[str, Any] = dict(result)
        cache.set(cache_key, payload, ttl=DASHBOARD_CACHE_TTL)
        resp = compat_success_response(
            legacy_payload=payload,
            status_code=200,
            message="Índice de sobrevivência calculado com sucesso",
            data=payload,
        )
        resp.headers["X-Cache"] = "MISS"
        return resp


class DashboardWeeklySummaryResource(MethodResource):
    @doc(**DASHBOARD_WEEKLY_SUMMARY_DOC)
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        period_raw = str(request.args.get("period", "1m")).strip()
        start_raw = str(request.args.get("start_date", "")).strip()
        end_raw = str(request.args.get("end_date", "")).strip()

        start_date: date | None = None
        end_date: date | None = None

        _dates_msg = "start_date e end_date são obrigatórios no formato YYYY-MM-DD."
        _period_msg = (
            "Período inválido. Use 1m, 3m, 6m ou forneça start_date e end_date."
        )
        if start_raw or end_raw:
            if not (_DATE_RE.match(start_raw) and _DATE_RE.match(end_raw)):
                return compat_error_response(
                    legacy_payload={"error": _dates_msg},
                    status_code=422,
                    message=_dates_msg,
                    error_code="VALIDATION_ERROR",
                )
            try:
                start_date = date.fromisoformat(start_raw)
                end_date = date.fromisoformat(end_raw)
            except ValueError:
                return compat_error_response(
                    legacy_payload={"error": "Data inválida."},
                    status_code=422,
                    message="Data inválida.",
                    error_code="VALIDATION_ERROR",
                )
            if start_date > end_date:
                _ord_msg = "start_date não pode ser posterior a end_date."
                return compat_error_response(
                    legacy_payload={"error": _ord_msg},
                    status_code=422,
                    message=_ord_msg,
                    error_code="VALIDATION_ERROR",
                )
            period = "custom"
        else:
            if period_raw not in _VALID_PERIODS:
                return compat_error_response(
                    legacy_payload={"error": _period_msg},
                    status_code=422,
                    message=_period_msg,
                    error_code="VALIDATION_ERROR",
                )
            period = period_raw

        cache = get_cache_service()
        cache_key = (
            f"dashboard:weekly-summary:{user_uuid}:{period}:{start_raw}:{end_raw}"
        )
        cached = cache.get(cache_key)
        if cached is not None:
            resp = compat_success_response(
                legacy_payload=cached,
                status_code=200,
                message="Resumo semanal calculado com sucesso",
                data=cached,
            )
            resp.headers["X-Cache"] = "HIT"
            return resp

        dependencies = get_transaction_dependencies()
        query_service = dependencies.transaction_query_service_factory(user_uuid)

        try:
            result = query_service.get_weekly_summary(
                period=period,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception:
            return compat_error_response(
                legacy_payload={"error": "Erro ao calcular resumo semanal"},
                status_code=500,
                message="Erro ao calcular resumo semanal",
                error_code="INTERNAL_ERROR",
            )

        payload: dict[str, Any] = dict(result)
        cache.set(cache_key, payload, ttl=DASHBOARD_CACHE_TTL)
        resp = compat_success_response(
            legacy_payload=payload,
            status_code=200,
            message="Resumo semanal calculado com sucesso",
            data=payload,
        )
        resp.headers["X-Cache"] = "MISS"
        return resp


__all__ = [
    "DashboardOverviewResource",
    "DashboardSurvivalIndexResource",
    "DashboardTrendsResource",
    "DashboardWeeklySummaryResource",
]
