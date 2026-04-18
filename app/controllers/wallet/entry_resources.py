from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response, request
from marshmallow import fields

from app.application.services.wallet_application_service import WalletApplicationError
from app.auth import current_user_id
from app.schemas.openapi.wallet.docs import (
    WALLET_ADD_DOC,
    WALLET_DELETE_DOC,
    WALLET_GET_DOC,
    WALLET_HISTORY_DOC,
    WALLET_LIST_DOC,
    WALLET_PATCH_DOC,
    WALLET_PUT_DOC,
    WALLET_UPDATE_SUCCESS_MESSAGE,
    WALLET_UPDATE_SUCCESSOR_ENDPOINT,
    WALLET_UPDATE_SUCCESSOR_METHOD,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .blueprint import wallet_bp
from .contracts import (
    application_error_response,
    compat_success,
    compat_success_deprecated,
)
from .dependencies import get_wallet_dependencies


@wallet_bp.route("", methods=["POST"])
@doc(**WALLET_ADD_DOC)
@jwt_required()
def add_wallet_entry() -> tuple[dict[str, Any], int]:
    user_id = current_user_id()
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
@doc(**WALLET_LIST_DOC)
@use_kwargs(
    {
        "page": fields.Int(load_default=1, validate=lambda x: x > 0),
        "per_page": fields.Int(load_default=10, validate=lambda x: 0 < x <= 100),
    },
    location="query",
)
@jwt_required()
def list_wallet_entries(page: int, per_page: int) -> tuple[dict[str, Any], int]:
    user_id = current_user_id()
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


@wallet_bp.route("/<uuid:investment_id>", methods=["GET"])
@doc(**WALLET_GET_DOC)
@jwt_required()
def get_wallet_entry(investment_id: UUID) -> tuple[dict[str, Any], int]:
    user_id = current_user_id()
    dependencies = get_wallet_dependencies()
    service = dependencies.wallet_application_service_factory(user_id)

    try:
        investment_data = service.get_entry(investment_id)
    except WalletApplicationError as exc:
        return application_error_response(exc)

    return compat_success(
        legacy_payload={"investment": investment_data},
        status_code=200,
        message="Investimento retornado com sucesso",
        data={"investment": investment_data},
    )


@wallet_bp.route("/<uuid:investment_id>/history", methods=["GET"])
@doc(**WALLET_HISTORY_DOC)
@jwt_required()
def get_wallet_history(investment_id: UUID) -> tuple[dict[str, Any], int]:
    user_id = current_user_id()
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


def _update_wallet_entry_data(
    investment_id: UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    user_id = current_user_id()
    dependencies = get_wallet_dependencies()
    service = dependencies.wallet_application_service_factory(user_id)

    return service.update_entry(investment_id, payload)


@wallet_bp.route("/<uuid:investment_id>", methods=["PATCH"])
@doc(**WALLET_PATCH_DOC)
@jwt_required()
def patch_wallet_entry(investment_id: UUID) -> tuple[dict[str, Any], int]:
    try:
        investment_data = _update_wallet_entry_data(
            investment_id,
            request.get_json() or {},
        )
    except WalletApplicationError as exc:
        return application_error_response(exc)

    return compat_success(
        legacy_payload={
            "message": WALLET_UPDATE_SUCCESS_MESSAGE,
            "investment": investment_data,
        },
        status_code=200,
        message=WALLET_UPDATE_SUCCESS_MESSAGE,
        data={"investment": investment_data},
    )


@wallet_bp.route("/<uuid:investment_id>", methods=["PUT"])
@doc(**WALLET_PUT_DOC)
@jwt_required()
def update_wallet_entry(investment_id: UUID) -> Response | tuple[dict[str, Any], int]:
    try:
        investment_data = _update_wallet_entry_data(
            investment_id,
            request.get_json() or {},
        )
    except WalletApplicationError as exc:
        return application_error_response(exc)

    return compat_success_deprecated(
        legacy_payload={
            "message": WALLET_UPDATE_SUCCESS_MESSAGE,
            "investment": investment_data,
        },
        status_code=200,
        message=WALLET_UPDATE_SUCCESS_MESSAGE,
        data={"investment": investment_data},
        successor_endpoint=WALLET_UPDATE_SUCCESSOR_ENDPOINT,
        successor_method=WALLET_UPDATE_SUCCESSOR_METHOD,
    )


@wallet_bp.route("/<uuid:investment_id>", methods=["DELETE"])
@doc(**WALLET_DELETE_DOC)
@jwt_required()
def delete_wallet_entry(investment_id: UUID) -> tuple[dict[str, Any], int]:
    user_id = current_user_id()
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
