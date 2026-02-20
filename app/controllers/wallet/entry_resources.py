# mypy: disable-error-code=misc

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import fields

from app.application.services.wallet_application_service import WalletApplicationError

from .blueprint import wallet_bp
from .contracts import application_error_response, compat_success
from .dependencies import get_wallet_dependencies


@wallet_bp.route("", methods=["POST"])
@doc(
    description=(
        "Adiciona um novo item à carteira do usuário.\n\n"
        "Você pode informar um valor fixo (como R$1000,00 em poupança) "
        "ou um ativo com ticker.\n\n"
        "Regras:\n"
        "- Se informar o campo 'ticker', o campo 'value' será ignorado.\n"
        "- Se não informar 'ticker', é obrigatório informar 'value'.\n"
        "- Se informar 'ticker', também é obrigatório informar 'quantity'.\n\n"
        "Exemplo com valor fixo:\n"
        "{'name': 'Poupança', 'value': 1500.00, 'register_date': "
        "'2024-07-01', 'should_be_on_wallet': true}\n\n"
        "Exemplo com ticker:\n"
        "{'name': 'Investimento PETR4', 'ticker': 'petr4', 'quantity': 10, "
        "'register_date': '2024-07-01', 'should_be_on_wallet': true}\n\n"
        "Resposta esperada:\n"
        "{'message': 'Ativo cadastrado com sucesso'}"
    ),
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    responses={
        201: {"description": "Ativo cadastrado com sucesso"},
        400: {"description": "Erro de validação ou ticker inválido"},
        401: {"description": "Token inválido"},
        500: {"description": "Erro interno"},
    },
)
@jwt_required()
def add_wallet_entry() -> tuple[dict[str, Any], int]:
    user_id = UUID(get_jwt_identity())
    payload = request.get_json() or {}
    dependencies = get_wallet_dependencies()
    service = dependencies.wallet_application_service_factory(user_id)

    try:
        investment_data = service.create_entry(payload)
    except WalletApplicationError as exc:
        return application_error_response(exc)

    legacy_payload = {
        "message": "Ativo cadastrado com sucesso",
        "investment": investment_data,
    }
    return compat_success(
        legacy_payload=legacy_payload,
        status_code=201,
        message="Ativo cadastrado com sucesso",
        data={"investment": investment_data},
    )


@wallet_bp.route("", methods=["GET"])
@doc(
    description="Lista os investimentos cadastrados na carteira com paginação.",
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        }
    },
    responses={
        200: {"description": "Lista paginada de investimentos"},
        401: {"description": "Token inválido"},
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
def list_wallet_entries(page: int, per_page: int) -> tuple[dict[str, Any], int]:
    user_id = UUID(get_jwt_identity())
    dependencies = get_wallet_dependencies()
    service = dependencies.wallet_application_service_factory(user_id)
    result = service.list_entries(page=page, per_page=per_page)
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
        message="Lista paginada de investimentos",
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


@wallet_bp.route("/<uuid:investment_id>/history", methods=["GET"])
@doc(
    description=(
        "Retorna o histórico de alterações de um investimento, "
        + "paginado e ordenado."
    ),
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={
        "investment_id": {"description": "ID do investimento"},
        "page": {"description": "Página desejada (default: 1)"},
        "per_page": {"description": "Itens por página (default: 5, 0 para todos)"},
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    responses={
        200: {"description": "Histórico paginado"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Investimento não encontrado"},
    },
)
@jwt_required()
def get_wallet_history(investment_id: UUID) -> tuple[dict[str, Any], int]:
    user_id = UUID(get_jwt_identity())
    dependencies = get_wallet_dependencies()
    service = dependencies.wallet_application_service_factory(user_id)
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=5, type=int)
    if page is None:
        page = 1
    if per_page is None:
        per_page = 5

    try:
        result = service.get_history(investment_id, page=page, per_page=per_page)
    except WalletApplicationError as exc:
        return application_error_response(exc)

    pagination = result["pagination"]
    history_response = {
        "data": result["items"],
        "total": pagination["total"],
        "page": pagination["page"],
        "page_size": pagination["page_size"],
        "has_next_page": pagination["has_next_page"],
    }
    return compat_success(
        legacy_payload=history_response,
        status_code=200,
        message="Histórico do investimento retornado com sucesso",
        data={"items": history_response["data"]},
        meta={
            "pagination": {
                "total": history_response["total"],
                "page": history_response["page"],
                "per_page": history_response["page_size"],
                "has_next_page": history_response["has_next_page"],
            }
        },
    )


@wallet_bp.route("/<uuid:investment_id>", methods=["PUT"])
@doc(
    description="Atualiza um investimento existente da carteira do usuário.",
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
        200: {"description": "Investimento atualizado com sucesso"},
        400: {"description": "Dados inválidos"},
        401: {"description": "Token inválido"},
        404: {"description": "Investimento não encontrado"},
    },
)
@jwt_required()
def update_wallet_entry(investment_id: UUID) -> tuple[dict[str, Any], int]:
    user_id = UUID(get_jwt_identity())
    payload = request.get_json() or {}
    dependencies = get_wallet_dependencies()
    service = dependencies.wallet_application_service_factory(user_id)

    try:
        investment_data = service.update_entry(investment_id, payload)
    except WalletApplicationError as exc:
        return application_error_response(exc)

    legacy_payload = {
        "message": "Investimento atualizado com sucesso",
        "investment": investment_data,
    }
    return compat_success(
        legacy_payload=legacy_payload,
        status_code=200,
        message="Investimento atualizado com sucesso",
        data={"investment": investment_data},
    )


@wallet_bp.route("/<uuid:investment_id>", methods=["DELETE"])
@doc(
    description="Deleta um investimento da carteira do usuário autenticado.",
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
        200: {"description": "Investimento deletado com sucesso"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão para deletar"},
        404: {"description": "Investimento não encontrado"},
    },
)
@jwt_required()
def delete_wallet_entry(investment_id: UUID) -> tuple[dict[str, Any], int]:
    user_id = UUID(get_jwt_identity())
    dependencies = get_wallet_dependencies()
    service = dependencies.wallet_application_service_factory(user_id)

    try:
        service.delete_entry(investment_id)
    except WalletApplicationError as exc:
        return application_error_response(exc)

    return compat_success(
        legacy_payload={"message": "Investimento deletado com sucesso"},
        status_code=200,
        message="Investimento deletado com sucesso",
        data={},
    )
