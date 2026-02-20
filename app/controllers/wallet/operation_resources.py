# mypy: disable-error-code=misc

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from flask import request
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import fields

from app.application.services.investment_application_service import (
    InvestmentApplicationError,
)

from .blueprint import wallet_bp
from .contracts import application_error_response, compat_success
from .dependencies import get_wallet_dependencies


@wallet_bp.route("/<uuid:investment_id>/operations", methods=["POST"])
@doc(
    description=(
        "Registra uma operação de investimento (buy/sell) para um item da carteira."
    ),
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
        201: {"description": "Operação criada com sucesso"},
        400: {"description": "Dados inválidos"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Investimento não encontrado"},
    },
)
@jwt_required()
def add_investment_operation(investment_id: UUID) -> tuple[dict[str, Any], int]:
    user_id: UUID = UUID(get_jwt_identity())
    payload: dict[str, Any] = request.get_json() or {}
    dependencies = get_wallet_dependencies()

    try:
        service = dependencies.investment_application_service_factory(user_id)
        operation_data = service.create_operation(investment_id, payload)
    except InvestmentApplicationError as exc:
        return application_error_response(exc)

    return compat_success(
        legacy_payload={
            "message": "Operação registrada com sucesso",
            "operation": operation_data,
        },
        status_code=201,
        message="Operação registrada com sucesso",
        data={"operation": operation_data},
    )


@wallet_bp.route("/<uuid:investment_id>/operations", methods=["GET"])
@doc(
    description=(
        "Lista operações de investimento de um item da carteira com paginação."
    ),
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={
        "investment_id": {"description": "ID do investimento"},
        "page": {"description": "Página desejada (default: 1)"},
        "per_page": {"description": "Itens por página (default: 10)"},
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    responses={
        200: {"description": "Lista paginada de operações"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Investimento não encontrado"},
    },
)
@use_kwargs(
    {
        "page": fields.Int(load_default=1, validate=lambda x: x > 0),
        "per_page": fields.Int(load_default=10, validate=lambda x: 0 < x <= 100),
    },
    location="query",
)
@jwt_required()
def list_investment_operations(
    investment_id: UUID, page: int, per_page: int
) -> tuple[dict[str, Any], int]:
    user_id: UUID = UUID(get_jwt_identity())
    dependencies = get_wallet_dependencies()

    try:
        service = dependencies.investment_application_service_factory(user_id)
        result = service.list_operations(investment_id, page=page, per_page=per_page)
    except InvestmentApplicationError as exc:
        return application_error_response(exc)

    items = result["items"]
    pagination = result["pagination"]
    legacy_payload = {
        "items": items,
        "total": pagination["total"],
        "page": pagination["page"],
        "per_page": pagination["per_page"],
        "pages": pagination["pages"],
    }
    return compat_success(
        legacy_payload=legacy_payload,
        status_code=200,
        message="Lista de operações retornada com sucesso",
        data={"items": items},
        meta={
            "pagination": {
                "total": pagination["total"],
                "page": pagination["page"],
                "per_page": pagination["per_page"],
                "pages": pagination["pages"],
            }
        },
    )


@wallet_bp.route(
    "/<uuid:investment_id>/operations/<uuid:operation_id>", methods=["PUT"]
)
@doc(
    description="Atualiza operação de investimento existente.",
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={
        "investment_id": {"description": "ID do investimento"},
        "operation_id": {"description": "ID da operação"},
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    responses={
        200: {"description": "Operação atualizada com sucesso"},
        400: {"description": "Dados inválidos"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Operação não encontrada"},
    },
)
@jwt_required()
def update_investment_operation(
    investment_id: UUID, operation_id: UUID
) -> tuple[dict[str, Any], int]:
    user_id: UUID = UUID(get_jwt_identity())
    payload: dict[str, Any] = request.get_json() or {}
    dependencies = get_wallet_dependencies()

    try:
        service = dependencies.investment_application_service_factory(user_id)
        operation_data = service.update_operation(investment_id, operation_id, payload)
    except InvestmentApplicationError as exc:
        return application_error_response(exc)

    return compat_success(
        legacy_payload={
            "message": "Operação atualizada com sucesso",
            "operation": operation_data,
        },
        status_code=200,
        message="Operação atualizada com sucesso",
        data={"operation": operation_data},
    )


@wallet_bp.route(
    "/<uuid:investment_id>/operations/<uuid:operation_id>", methods=["DELETE"]
)
@doc(
    description="Remove operação de investimento.",
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={
        "investment_id": {"description": "ID do investimento"},
        "operation_id": {"description": "ID da operação"},
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    responses={
        200: {"description": "Operação removida com sucesso"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Operação não encontrada"},
    },
)
@jwt_required()
def delete_investment_operation(
    investment_id: UUID, operation_id: UUID
) -> tuple[dict[str, Any], int]:
    user_id: UUID = UUID(get_jwt_identity())
    dependencies = get_wallet_dependencies()

    try:
        service = dependencies.investment_application_service_factory(user_id)
        service.delete_operation(investment_id, operation_id)
    except InvestmentApplicationError as exc:
        return application_error_response(exc)

    return compat_success(
        legacy_payload={"message": "Operação removida com sucesso"},
        status_code=200,
        message="Operação removida com sucesso",
        data={},
    )


@wallet_bp.route("/<uuid:investment_id>/operations/summary", methods=["GET"])
@doc(
    description="Resumo agregado das operações de um investimento.",
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
        200: {"description": "Resumo retornado com sucesso"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Investimento não encontrado"},
    },
)
@jwt_required()
def get_investment_operations_summary(
    investment_id: UUID,
) -> tuple[dict[str, Any], int]:
    user_id: UUID = UUID(get_jwt_identity())
    dependencies = get_wallet_dependencies()

    try:
        service = dependencies.investment_application_service_factory(user_id)
        summary = service.get_summary(investment_id)
    except InvestmentApplicationError as exc:
        return application_error_response(exc)

    return compat_success(
        legacy_payload={"summary": summary},
        status_code=200,
        message="Resumo de operações retornado com sucesso",
        data={"summary": summary},
    )


@wallet_bp.route("/<uuid:investment_id>/operations/position", methods=["GET"])
@doc(
    description=(
        "Retorna posição atual e custo médio do investimento com base nas "
        "operações registradas."
    ),
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
        200: {"description": "Posição retornada com sucesso"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Investimento não encontrado"},
    },
)
@jwt_required()
def get_investment_operations_position(
    investment_id: UUID,
) -> tuple[dict[str, Any], int]:
    user_id: UUID = UUID(get_jwt_identity())
    dependencies = get_wallet_dependencies()

    try:
        service = dependencies.investment_application_service_factory(user_id)
        position = service.get_position(investment_id)
    except InvestmentApplicationError as exc:
        return application_error_response(exc)

    return compat_success(
        legacy_payload={"position": position},
        status_code=200,
        message="Posição de operações retornada com sucesso",
        data={"position": position},
    )


@wallet_bp.route("/<uuid:investment_id>/operations/invested-amount", methods=["GET"])
@doc(
    description=(
        "Retorna o valor investido no dia informado, considerando operações "
        "de compra e venda do investimento."
    ),
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={
        "investment_id": {"description": "ID do investimento"},
        "date": {
            "description": "Data da operação no formato YYYY-MM-DD",
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
        200: {"description": "Cálculo retornado com sucesso"},
        400: {"description": "Parâmetro inválido"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Investimento não encontrado"},
    },
)
@use_kwargs(
    {"date": fields.Date(required=True)},
    location="query",
)
@jwt_required()
def get_invested_amount_by_date(
    investment_id: UUID, date: date
) -> tuple[dict[str, Any], int]:
    user_id: UUID = UUID(get_jwt_identity())
    dependencies = get_wallet_dependencies()

    try:
        service = dependencies.investment_application_service_factory(user_id)
        result = service.get_invested_amount_by_date(investment_id, date)
    except InvestmentApplicationError as exc:
        return application_error_response(exc)

    return compat_success(
        legacy_payload={"result": result},
        status_code=200,
        message="Valor investido no período retornado com sucesso",
        data={"result": result},
    )
