from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response, request

from app.auth import current_user_id
from app.docs.openapi_helpers import deprecated_headers_doc
from app.services.investment_operation_service import InvestmentOperationError
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import wallet_bp
from .contracts import (
    compat_success,
    compat_success_deprecated,
    operation_error_response,
    parse_optional_query_date,
    validation_error_response,
)
from .dependencies import get_wallet_dependencies

LEGACY_WALLET_HISTORY_START_PARAM = "startDate"
LEGACY_WALLET_HISTORY_END_PARAM = "finalDate"
CANONICAL_WALLET_HISTORY_START_PARAM = "start_date"
CANONICAL_WALLET_HISTORY_END_PARAM = "end_date"
WALLET_HISTORY_DATE_ALIAS_WARNING = (
    '299 - "Query params startDate/finalDate are deprecated; use start_date/end_date"'
)


def _resolve_wallet_history_period_args() -> tuple[str | None, str | None, bool]:
    raw_start_date = request.args.get(CANONICAL_WALLET_HISTORY_START_PARAM)
    raw_end_date = request.args.get(CANONICAL_WALLET_HISTORY_END_PARAM)
    uses_legacy_alias = False

    legacy_start_date = request.args.get(LEGACY_WALLET_HISTORY_START_PARAM)
    legacy_end_date = request.args.get(LEGACY_WALLET_HISTORY_END_PARAM)
    if legacy_start_date is not None or legacy_end_date is not None:
        uses_legacy_alias = True
    if raw_start_date is None:
        raw_start_date = legacy_start_date
    if raw_end_date is None:
        raw_end_date = legacy_end_date
    return raw_start_date, raw_end_date, uses_legacy_alias


@wallet_bp.route("/valuation", methods=["GET"])
@doc(
    description=(
        "Retorna a valorização atual consolidada da carteira do usuário, "
        "com cálculo por investimento."
    ),
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    responses={
        200: {"description": "Valorização retornada com sucesso"},
        401: {"description": "Token inválido"},
    },
)
@jwt_required()
def get_portfolio_valuation() -> tuple[dict[str, Any], int]:
    user_id: UUID = current_user_id()
    dependencies = get_wallet_dependencies()
    service = dependencies.portfolio_valuation_service_factory(user_id)
    payload = service.get_portfolio_current_valuation()
    return compat_success(
        legacy_payload=payload,
        status_code=200,
        message="Valorização da carteira retornada com sucesso",
        data=payload,
    )


@wallet_bp.route("/valuation/history", methods=["GET"])
@doc(
    description=(
        "Retorna histórico diário de evolução da carteira por período, com "
        "totais de compra/venda e valor líquido investido acumulado."
    ),
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={
        "start_date": {
            "in": "query",
            "description": "Data inicial (YYYY-MM-DD). Opcional.",
            "required": False,
        },
        "end_date": {
            "in": "query",
            "description": "Data final (YYYY-MM-DD). Opcional.",
            "required": False,
        },
        "startDate": {
            "in": "query",
            "description": "Alias legado de `start_date`.",
            "required": False,
            "deprecated": True,
        },
        "finalDate": {
            "in": "query",
            "description": "Alias legado de `end_date`.",
            "required": False,
            "deprecated": True,
        },
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    responses={
        200: {
            "description": "Histórico retornado com sucesso",
            "headers": deprecated_headers_doc(
                successor_field="start_date,end_date",
                warning=WALLET_HISTORY_DATE_ALIAS_WARNING,
            ),
        },
        400: {"description": "Parâmetros inválidos"},
        401: {"description": "Token inválido"},
    },
)
@jwt_required()
def get_portfolio_valuation_history() -> Response | tuple[dict[str, Any], int]:
    user_id: UUID = current_user_id()
    dependencies = get_wallet_dependencies()

    raw_start_date, raw_final_date, uses_legacy_alias = (
        _resolve_wallet_history_period_args()
    )

    try:
        start_date = parse_optional_query_date(
            raw_start_date,
            CANONICAL_WALLET_HISTORY_START_PARAM,
        )
        final_date = parse_optional_query_date(
            raw_final_date,
            CANONICAL_WALLET_HISTORY_END_PARAM,
        )
    except ValueError as exc:
        return validation_error_response(
            exc=exc,
            fallback_message="Parâmetros de período inválidos.",
        )

    service = dependencies.portfolio_history_service_factory(user_id)
    try:
        payload = service.get_history(start_date=start_date, end_date=final_date)
    except ValueError as exc:
        return validation_error_response(
            exc=exc,
            fallback_message="Período informado é inválido.",
        )

    if uses_legacy_alias:
        return compat_success_deprecated(
            legacy_payload=payload,
            status_code=200,
            message="Histórico da carteira retornado com sucesso",
            data=payload,
            successor_field="start_date,end_date",
            warning=WALLET_HISTORY_DATE_ALIAS_WARNING,
        )

    return compat_success(
        legacy_payload=payload,
        status_code=200,
        message="Histórico da carteira retornado com sucesso",
        data=payload,
    )


@wallet_bp.route(
    "/<uuid:investment_id>/valuation",
    methods=["GET"],
)
@doc(
    description="Retorna a valorização atual de um investimento específico.",
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={
        "investment_id": {"description": "ID do investimento"},
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    responses={
        200: {"description": "Valorização retornada com sucesso"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Investimento não encontrado"},
    },
)
@jwt_required()
def get_investment_valuation(investment_id: UUID) -> tuple[dict[str, Any], int]:
    user_id: UUID = current_user_id()
    dependencies = get_wallet_dependencies()
    service = dependencies.portfolio_valuation_service_factory(user_id)
    try:
        valuation = service.get_investment_current_valuation(investment_id)
    except InvestmentOperationError as exc:
        return operation_error_response(exc)

    return compat_success(
        legacy_payload={"valuation": valuation},
        status_code=200,
        message="Valorização do investimento retornada com sucesso",
        data={"valuation": valuation},
    )
