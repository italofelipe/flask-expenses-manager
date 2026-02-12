# mypy: disable-error-code=misc

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from flask import current_app, request
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError, fields

from app.extensions.database import db
from app.models.wallet import Wallet
from app.schemas.wallet_schema import WalletSchema
from app.utils.datetime_utils import iso_utc_now_naive
from app.utils.pagination import PaginatedResponse

from .blueprint import wallet_bp
from .contracts import compat_error, compat_success
from .dependencies import get_wallet_dependencies
from .serializers import serialize_wallet_item, serialize_wallet_items


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
    """Adiciona um novo item à carteira do usuário com validação de ticker."""
    user_id: UUID = UUID(get_jwt_identity())
    data: dict[str, Any] = request.get_json()

    schema = WalletSchema()

    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return compat_error(
            legacy_payload={"error": "Dados inválidos", "messages": str(err.messages)},
            status_code=400,
            message="Dados inválidos",
            error_code="VALIDATION_ERROR",
            details={"messages": err.messages},
        )

    dependencies = get_wallet_dependencies()
    estimated_value = dependencies.calculate_estimated_value(validated_data)
    validated_data["estimated_value_on_create_date"] = estimated_value

    try:
        new_wallet = Wallet(
            user_id=user_id,
            name=validated_data["name"],
            value=validated_data.get("value"),
            estimated_value_on_create_date=validated_data[
                "estimated_value_on_create_date"
            ],
            ticker=validated_data.get("ticker"),
            quantity=validated_data.get("quantity"),
            asset_class=str(validated_data.get("asset_class", "custom")).lower(),
            annual_rate=validated_data.get("annual_rate"),
            register_date=validated_data.get("register_date", date.today()),
            target_withdraw_date=validated_data.get("target_withdraw_date"),
            should_be_on_wallet=validated_data["should_be_on_wallet"],
        )
        db.session.add(new_wallet)
        db.session.commit()

        investment_data = serialize_wallet_item(new_wallet)
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro inesperado ao criar investimento.")
        return compat_error(
            legacy_payload={"error": "Internal Server Error"},
            status_code=500,
            message="Internal Server Error",
            error_code="INTERNAL_ERROR",
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
        "page": fields.Int(missing=1, validate=lambda x: x > 0),
        "per_page": fields.Int(missing=10, validate=lambda x: 0 < x <= 100),
    },
    location="query",
)
@jwt_required()
def list_wallet_entries(page: int, per_page: int) -> tuple[dict[str, Any], int]:
    """Lista paginada dos investimentos do usuário autenticado."""
    user_id: UUID = UUID(get_jwt_identity())

    pagination = (
        Wallet.query.filter_by(user_id=user_id)
        .order_by(Wallet.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    items = serialize_wallet_items(pagination.items)
    legacy_payload = {
        "items": items,
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }
    return compat_success(
        legacy_payload=legacy_payload,
        status_code=200,
        message="Lista paginada de investimentos",
        data={"items": items},
        meta={
            "pagination": {
                "total": pagination.total,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
            }
        },
    )


@wallet_bp.route("/<uuid:investment_id>/history", methods=["GET"])
@doc(
    description=(
        "Retorna o histórico de alterações de um investimento, " "paginado e ordenado."
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
    """Retorna histórico de alterações de um investimento específico, paginado."""
    user_id: UUID = UUID(get_jwt_identity())
    investment = Wallet.query.filter_by(id=investment_id).first()
    if not investment:
        return compat_error(
            legacy_payload={"error": "Investimento não encontrado"},
            status_code=404,
            message="Investimento não encontrado",
            error_code="NOT_FOUND",
        )
    if str(investment.user_id) != str(user_id):
        return compat_error(
            legacy_payload={
                "error": "Você não tem permissão para ver o histórico "
                "deste investimento."
            },
            status_code=403,
            message="Você não tem permissão para ver o histórico deste investimento.",
            error_code="FORBIDDEN",
        )

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=5, type=int)

    history = investment.history or []

    def _sort_key(item: dict[str, Any]) -> tuple[Any, str]:
        qty = item.get("originalQuantity", 0) or 0
        date_str = item.get("changeDate", "")
        return (qty, date_str)

    sorted_history = sorted(history, key=_sort_key, reverse=True)
    total = len(sorted_history)

    if per_page < 1 or per_page > 100:
        return compat_error(
            legacy_payload={"error": "Parâmetro 'per_page' inválido. Use 1-100."},
            status_code=400,
            message="Parâmetro 'per_page' inválido. Use 1-100.",
            error_code="VALIDATION_ERROR",
        )

    start = (page - 1) * per_page
    end = start + per_page
    items = sorted_history[start:end]
    current_page = page
    current_per_page = per_page

    response = PaginatedResponse.format(
        data=items,
        total=total,
        page=current_page,
        page_size=current_per_page,
    )
    return compat_success(
        legacy_payload=response,
        status_code=200,
        message="Histórico do investimento retornado com sucesso",
        data={"items": response["data"]},
        meta={
            "pagination": {
                "total": response["total"],
                "page": response["page"],
                "per_page": response["page_size"],
                "has_next_page": response["has_next_page"],
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
    """Atualiza um investimento existente (pertencente ao usuário autenticado)."""
    user_id: UUID = UUID(get_jwt_identity())
    data: dict[str, Any] = request.get_json()

    investment = Wallet.query.filter_by(id=investment_id).first()
    if investment and str(investment.user_id) != str(user_id):
        return compat_error(
            legacy_payload={
                "error": "Você não tem permissão para editar este investimento."
            },
            status_code=403,
            message="Você não tem permissão para editar este investimento.",
            error_code="FORBIDDEN",
        )
    if not investment:
        return compat_error(
            legacy_payload={"error": "Investimento não encontrado"},
            status_code=404,
            message="Investimento não encontrado",
            error_code="NOT_FOUND",
        )

    schema = WalletSchema(partial=True)
    try:
        validated_data = schema.load(data, partial=True)
    except ValidationError as err:
        return compat_error(
            legacy_payload={"error": "Dados inválidos", "messages": str(err.messages)},
            status_code=400,
            message="Dados inválidos",
            error_code="VALIDATION_ERROR",
            details={"messages": err.messages},
        )

    _update_investment_history(investment, validated_data)
    _apply_validated_fields(investment, validated_data)

    return _commit_investment_update(investment)


def _build_quantity_change(
    investment: Wallet,
    old_quantity: Any,
    old_estimated: Any,
) -> dict[str, Any]:
    """Constrói registro de histórico para mudança de quantidade."""
    dependencies = get_wallet_dependencies()
    price = dependencies.get_market_price(investment.ticker)
    return {
        "changeDate": iso_utc_now_naive(),
        "originalQuantity": old_quantity,
        "estimated_value_on_create_date": (
            float(old_estimated)
            if isinstance(old_estimated, Decimal)
            else old_estimated
        ),
        "originalValue": (
            float(price) if isinstance(price, (int, float, Decimal)) else price
        ),
    }


def _build_value_change(old_value: Any) -> dict[str, Any]:
    """Constrói registro de histórico para mudança de valor."""
    return {
        "originalValue": (
            float(old_value) if isinstance(old_value, Decimal) else old_value
        ),
        "changeDate": iso_utc_now_naive(),
    }


def _update_investment_history(
    investment: Wallet,
    validated_data: dict[str, Any],
) -> None:
    """Atualiza o histórico do investimento se houver mudanças relevantes."""
    old_quantity = investment.quantity
    old_estimated = investment.estimated_value_on_create_date
    old_value = investment.value

    changes: dict[str, Any] = {}
    if "quantity" in validated_data and validated_data["quantity"] != old_quantity:
        changes = _build_quantity_change(investment, old_quantity, old_estimated)
    elif "value" in validated_data and validated_data["value"] != old_value:
        changes = _build_value_change(old_value)

    if changes:
        history = investment.history or []
        history.append(changes)
        investment.history = history


def _apply_validated_fields(investment: Wallet, validated_data: dict[str, Any]) -> None:
    """Aplica campos validados e recalcula valor estimado."""
    for field, value in validated_data.items():
        if field == "asset_class" and value is not None:
            setattr(investment, field, str(value).lower())
            continue
        setattr(investment, field, value)

    recalc_data = {
        **validated_data,
        "ticker": investment.ticker,
        "value": investment.value,
        "quantity": investment.quantity,
    }
    dependencies = get_wallet_dependencies()
    new_estimate = dependencies.calculate_estimated_value(recalc_data)
    investment.estimated_value_on_create_date = new_estimate


def _commit_investment_update(investment: Wallet) -> tuple[dict[str, Any], int]:
    """Persiste as alterações e retorna resposta formatada."""
    try:
        db.session.commit()
        investment_data = serialize_wallet_item(investment)
        investment_data["history"] = investment.history
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro inesperado ao atualizar investimento.")
        return compat_error(
            legacy_payload={"error": "Erro interno"},
            status_code=500,
            message="Erro interno",
            error_code="INTERNAL_ERROR",
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
    """Deleta um investimento existente (pertencente ao usuário autenticado)."""
    user_id: UUID = UUID(get_jwt_identity())
    investment = Wallet.query.filter_by(id=investment_id).first()
    if not investment:
        return compat_error(
            legacy_payload={"error": "Investimento não encontrado"},
            status_code=404,
            message="Investimento não encontrado",
            error_code="NOT_FOUND",
        )
    if str(investment.user_id) != str(user_id):
        return compat_error(
            legacy_payload={
                "error": "Você não tem permissão para deletar este investimento."
            },
            status_code=403,
            message="Você não tem permissão para deletar este investimento.",
            error_code="FORBIDDEN",
        )
    try:
        db.session.delete(investment)
        db.session.commit()
        return compat_success(
            legacy_payload={"message": "Investimento deletado com sucesso"},
            status_code=200,
            message="Investimento deletado com sucesso",
            data={},
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao deletar investimento.")
        return compat_error(
            legacy_payload={"error": "Erro ao deletar investimento"},
            status_code=500,
            message="Erro ao deletar investimento",
            error_code="INTERNAL_ERROR",
        )
