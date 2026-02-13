# mypy: disable-error-code=misc

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request
from flask_apispec import doc
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.investment_operation_service import InvestmentOperationError

from .blueprint import wallet_bp
from .contracts import (
    compat_success,
    operation_error_response,
    parse_optional_query_date,
    validation_error_response,
)
from .dependencies import get_wallet_dependencies


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
    user_id: UUID = UUID(get_jwt_identity())
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
        "startDate": {
            "in": "query",
            "description": "Data inicial (YYYY-MM-DD). Opcional.",
            "required": False,
        },
        "finalDate": {
            "in": "query",
            "description": "Data final (YYYY-MM-DD). Opcional.",
            "required": False,
        },
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    responses={
        200: {"description": "Histórico retornado com sucesso"},
        400: {"description": "Parâmetros inválidos"},
        401: {"description": "Token inválido"},
    },
)
@jwt_required()
def get_portfolio_valuation_history() -> tuple[dict[str, Any], int]:
    user_id: UUID = UUID(get_jwt_identity())
    dependencies = get_wallet_dependencies()

    raw_start_date = request.args.get("startDate")
    raw_final_date = request.args.get("finalDate")

    try:
        start_date = parse_optional_query_date(raw_start_date, "startDate")
        final_date = parse_optional_query_date(raw_final_date, "finalDate")
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
    user_id: UUID = UUID(get_jwt_identity())
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
