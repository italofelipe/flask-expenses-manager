from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict
from uuid import UUID

from flask import Blueprint, request
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError, fields

from app.extensions.database import db
from app.models.wallet import Wallet
from app.schemas.wallet_schema import WalletSchema
from app.services.investment_service import InvestmentService

# Import PaginatedResponse for paginated investment history
from app.utils.pagination import PaginatedResponse
from app.utils.response_builder import error_payload, success_payload

wallet_bp = Blueprint("wallet", __name__, url_prefix="/wallet")
CONTRACT_HEADER = "X-API-Contract"
CONTRACT_V2 = "v2"


def _is_v2_contract() -> bool:
    header_value = str(request.headers.get(CONTRACT_HEADER, "")).strip().lower()
    return header_value == CONTRACT_V2


def _compat_success(
    *,
    legacy_payload: Dict[str, Any],
    status_code: int,
    message: str,
    data: Dict[str, Any],
    meta: Dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    if _is_v2_contract():
        return success_payload(message=message, data=data, meta=meta), status_code
    return legacy_payload, status_code


def _compat_error(
    *,
    legacy_payload: Dict[str, Any],
    status_code: int,
    message: str,
    error_code: str,
    details: Dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    if _is_v2_contract():
        return (
            error_payload(
                message=message,
                code=error_code,
                details=details,
            ),
            status_code,
        )
    return legacy_payload, status_code


@wallet_bp.route("", methods=["POST"])  # type: ignore[misc]
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
)  # type: ignore[misc]
@jwt_required()  # type: ignore[misc]
def add_wallet_entry() -> tuple[dict[str, Any], int]:
    """Adiciona um novo item à carteira do usuário com validação de ticker."""
    user_id: UUID = UUID(get_jwt_identity())
    data: Dict[str, Any] = request.get_json()

    schema = WalletSchema()

    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return _compat_error(
            legacy_payload={"error": "Dados inválidos", "messages": str(err.messages)},
            status_code=400,
            message="Dados inválidos",
            error_code="VALIDATION_ERROR",
            details={"messages": err.messages},
        )

    # Calcula valor estimado
    estimated_value = InvestmentService.calculate_estimated_value(validated_data)
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
            register_date=validated_data.get("register_date", date.today()),
            target_withdraw_date=validated_data.get("target_withdraw_date"),
            should_be_on_wallet=validated_data["should_be_on_wallet"],
        )
        db.session.add(new_wallet)
        db.session.commit()
        schema = WalletSchema()
        investment_data = schema.dump(new_wallet)
        # Omite campos conforme tipo de investimento
        if investment_data.get("ticker") is None:
            # hardcoded: omit ticker, quantity, and estimated value
            investment_data.pop("estimated_value_on_create_date", None)
            investment_data.pop("ticker", None)
            investment_data.pop("quantity", None)
        else:
            # ticker: omit value
            investment_data.pop("value", None)
        legacy_payload = {
            "message": "Ativo cadastrado com sucesso",
            "investment": investment_data,
        }
        return _compat_success(
            legacy_payload=legacy_payload,
            status_code=201,
            message="Ativo cadastrado com sucesso",
            data={"investment": investment_data},
        )
    except Exception as e:
        db.session.rollback()
        import traceback

        print("Erro inesperado:", traceback.format_exc())
        print("Tipo:", type(e), "| Args:", e.args)
        return _compat_error(
            legacy_payload={"error": "Internal Server Error", "message": str(e)},
            status_code=500,
            message="Internal Server Error",
            error_code="INTERNAL_ERROR",
            details={"exception": str(e)},
        )


# GET /wallet - Listar investimentos do usuário com paginação
@wallet_bp.route("", methods=["GET"])  # type: ignore[misc]
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
)  # type: ignore[misc]
@use_kwargs(
    {
        "page": fields.Int(missing=1, validate=lambda x: x > 0),
        "per_page": fields.Int(missing=10, validate=lambda x: 0 < x <= 100),
    },
    location="query",
)  # type: ignore[misc]
@jwt_required()  # type: ignore[misc]
def list_wallet_entries(page: int, per_page: int) -> tuple[dict[str, Any], int]:
    """Lista paginada dos investimentos do usuário autenticado."""
    user_id: UUID = UUID(get_jwt_identity())

    pagination = (
        Wallet.query.filter_by(user_id=user_id)
        .order_by(Wallet.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    schema = WalletSchema(many=True)
    items = schema.dump(pagination.items)
    for item in items:
        if item.get("ticker") is None:
            # hardcoded: omit ticker, quantity, and estimated value
            item.pop("estimated_value_on_create_date", None)
            item.pop("ticker", None)
            item.pop("quantity", None)
        else:
            # ticker: omit value
            item.pop("value", None)
    legacy_payload = {
        "items": items,
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }
    return _compat_success(
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


# GET /wallet/<uuid:investment_id>/history - Histórico paginado de um investimento
@wallet_bp.route("/<uuid:investment_id>/history", methods=["GET"])  # type: ignore[misc]
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
)  # type: ignore[misc]
@jwt_required()  # type: ignore[misc]
def get_wallet_history(investment_id: UUID) -> tuple[Dict[str, Any], int]:
    """Retorna histórico de alterações de um investimento específico, paginado."""
    user_id: UUID = UUID(get_jwt_identity())
    investment = Wallet.query.filter_by(id=investment_id).first()
    if not investment:
        return _compat_error(
            legacy_payload={"error": "Investimento não encontrado"},
            status_code=404,
            message="Investimento não encontrado",
            error_code="NOT_FOUND",
        )
    if str(investment.user_id) != str(user_id):
        return _compat_error(
            legacy_payload={
                "error": "Você não tem permissão para ver o histórico "
                "deste investimento."
            },
            status_code=403,
            message="Você não tem permissão para ver o histórico deste investimento.",
            error_code="FORBIDDEN",
        )

    # Parâmetros de paginação
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=5, type=int)

    history = investment.history or []

    # Ordena por originalQuantity e changeDate, ambos em ordem decrescente
    def _sort_key(item: Dict[str, Any]) -> tuple[Any, str]:
        qty = item.get("originalQuantity", 0) or 0
        date_str = item.get("changeDate", "")
        return (qty, date_str)

    sorted_history = sorted(history, key=_sort_key, reverse=True)
    total = len(sorted_history)

    # Seleciona página
    if per_page <= 0:
        items = sorted_history
        current_per_page = total or 1
        current_page = 1
    else:
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
    return _compat_success(
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


# PUT /wallet/<uuid:investment_id> - Atualizar investimento existente
@wallet_bp.route("/<uuid:investment_id>", methods=["PUT"])  # type: ignore[misc]
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
)  # type: ignore[misc]
@jwt_required()  # type: ignore[misc]
def update_wallet_entry(investment_id: UUID) -> tuple[dict[str, Any], int]:
    """Atualiza um investimento existente (pertencente ao usuário autenticado)."""
    user_id: UUID = UUID(get_jwt_identity())
    data: Dict[str, Any] = request.get_json()

    investment = Wallet.query.filter_by(id=investment_id).first()
    if investment and str(investment.user_id) != str(user_id):
        return _compat_error(
            legacy_payload={
                "error": "Você não tem permissão para editar este investimento."
            },
            status_code=403,
            message="Você não tem permissão para editar este investimento.",
            error_code="FORBIDDEN",
        )
    if not investment:
        return _compat_error(
            legacy_payload={"error": "Investimento não encontrado"},
            status_code=404,
            message="Investimento não encontrado",
            error_code="NOT_FOUND",
        )

    schema = WalletSchema(partial=True)
    try:
        validated_data = schema.load(data, partial=True)
    except ValidationError as err:
        return _compat_error(
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
    investment: Wallet, old_quantity: Any, old_estimated: Any
) -> Dict[str, Any]:
    """Constrói registro de histórico para mudança de quantidade."""
    price = InvestmentService.get_market_price(investment.ticker)
    return {
        "changeDate": datetime.utcnow().isoformat(),
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


def _build_value_change(old_value: Any) -> Dict[str, Any]:
    """Constrói registro de histórico para mudança de valor."""
    return {
        "originalValue": (
            float(old_value) if isinstance(old_value, Decimal) else old_value
        ),
        "changeDate": datetime.utcnow().isoformat(),
    }


def _update_investment_history(
    investment: Wallet, validated_data: Dict[str, Any]
) -> None:
    """Atualiza o histórico do investimento se houver mudanças relevantes."""
    old_quantity = investment.quantity
    old_estimated = investment.estimated_value_on_create_date
    old_value = investment.value

    changes: Dict[str, Any] = {}
    if "quantity" in validated_data and validated_data["quantity"] != old_quantity:
        changes = _build_quantity_change(investment, old_quantity, old_estimated)
    elif "value" in validated_data and validated_data["value"] != old_value:
        changes = _build_value_change(old_value)

    if changes:
        history = investment.history or []
        history.append(changes)
        investment.history = history


def _apply_validated_fields(investment: Wallet, validated_data: Dict[str, Any]) -> None:
    """Aplica campos validados e recalcula valor estimado."""
    for field, value in validated_data.items():
        setattr(investment, field, value)

    recalc_data = {
        **validated_data,
        "ticker": investment.ticker,
        "value": investment.value,
        "quantity": investment.quantity,
    }
    new_estimate = InvestmentService.calculate_estimated_value(recalc_data)
    investment.estimated_value_on_create_date = new_estimate


def _commit_investment_update(investment: Wallet) -> tuple[dict[str, Any], int]:
    """Persiste as alterações e retorna resposta formatada."""
    try:
        db.session.commit()
        schema = WalletSchema()
        investment_data = schema.dump(investment)
        if investment_data.get("ticker") is None:
            investment_data.pop("estimated_value_on_create_date", None)
            investment_data.pop("ticker", None)
            investment_data.pop("quantity", None)
        else:
            investment_data.pop("value", None)
        investment_data["history"] = investment.history
        legacy_payload = {
            "message": "Investimento atualizado com sucesso",
            "investment": investment_data,
        }
        return _compat_success(
            legacy_payload=legacy_payload,
            status_code=200,
            message="Investimento atualizado com sucesso",
            data={"investment": investment_data},
        )
    except Exception as e:
        db.session.rollback()
        import traceback

        print("Erro inesperado:", traceback.format_exc())
        return _compat_error(
            legacy_payload={"error": "Erro interno", "message": str(e)},
            status_code=500,
            message="Erro interno",
            error_code="INTERNAL_ERROR",
            details={"exception": str(e)},
        )


# DELETE /wallet/<uuid:investment_id> - Deletar investimento existente
@wallet_bp.route("/<uuid:investment_id>", methods=["DELETE"])  # type: ignore[misc]
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
)  # type: ignore[misc]
@jwt_required()  # type: ignore[misc]
def delete_wallet_entry(investment_id: UUID) -> tuple[dict[str, Any], int]:
    """Deleta um investimento existente (pertencente ao usuário autenticado)."""
    user_id: UUID = UUID(get_jwt_identity())
    investment = Wallet.query.filter_by(id=investment_id).first()
    if not investment:
        return _compat_error(
            legacy_payload={"error": "Investimento não encontrado"},
            status_code=404,
            message="Investimento não encontrado",
            error_code="NOT_FOUND",
        )
    # Verifica permissão de usuário
    if str(investment.user_id) != str(user_id):
        return _compat_error(
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
        return _compat_success(
            legacy_payload={"message": "Investimento deletado com sucesso"},
            status_code=200,
            message="Investimento deletado com sucesso",
            data={},
        )
    except Exception as e:
        db.session.rollback()
        return _compat_error(
            legacy_payload={"error": "Erro ao deletar investimento", "message": str(e)},
            status_code=500,
            message="Erro ao deletar investimento",
            error_code="INTERNAL_ERROR",
            details={"exception": str(e)},
        )
