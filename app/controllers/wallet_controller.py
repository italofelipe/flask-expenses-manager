# mypy: disable-error-code=misc

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict
from uuid import UUID

from flask import Blueprint, current_app, request
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError, fields

from app.extensions.database import db
from app.models.wallet import Wallet
from app.schemas.wallet_schema import WalletSchema
from app.services.investment_operation_service import (
    InvestmentOperationError,
    InvestmentOperationService,
)
from app.services.investment_service import InvestmentService
from app.services.portfolio_history_service import PortfolioHistoryService
from app.services.portfolio_valuation_service import PortfolioValuationService

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


def _operation_error_response(
    exc: InvestmentOperationError,
) -> tuple[dict[str, Any], int]:
    return _compat_error(
        legacy_payload={"error": exc.message, "details": exc.details},
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.code,
        details=exc.details,
    )


def _parse_optional_query_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"Parâmetro '{field_name}' inválido. Use o formato YYYY-MM-DD."
        )


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
            asset_class=str(validated_data.get("asset_class", "custom")).lower(),
            annual_rate=validated_data.get("annual_rate"),
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro inesperado ao criar investimento.")
        return _compat_error(
            legacy_payload={"error": "Internal Server Error"},
            status_code=500,
            message="Internal Server Error",
            error_code="INTERNAL_ERROR",
        )


# GET /wallet - Listar investimentos do usuário com paginação
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
    if per_page < 1 or per_page > 100:
        return _compat_error(
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
    payload: Dict[str, Any] = request.get_json() or {}
    try:
        service = InvestmentOperationService(user_id)
        operation = service.create_operation(investment_id, payload)
    except InvestmentOperationError as exc:
        return _operation_error_response(exc)

    operation_data = InvestmentOperationService.serialize(operation)
    return _compat_success(
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
        "page": fields.Int(missing=1, validate=lambda x: x > 0),
        "per_page": fields.Int(missing=10, validate=lambda x: 0 < x <= 100),
    },
    location="query",
)
@jwt_required()
def list_investment_operations(
    investment_id: UUID, page: int, per_page: int
) -> tuple[dict[str, Any], int]:
    user_id: UUID = UUID(get_jwt_identity())
    try:
        service = InvestmentOperationService(user_id)
        operations, pagination = service.list_operations(investment_id, page, per_page)
    except InvestmentOperationError as exc:
        return _operation_error_response(exc)

    items = [InvestmentOperationService.serialize(item) for item in operations]
    legacy_payload = {
        "items": items,
        "total": pagination["total"],
        "page": pagination["page"],
        "per_page": pagination["per_page"],
        "pages": pagination["pages"],
    }
    return _compat_success(
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
    payload: Dict[str, Any] = request.get_json() or {}

    try:
        service = InvestmentOperationService(user_id)
        operation = service.update_operation(investment_id, operation_id, payload)
    except InvestmentOperationError as exc:
        return _operation_error_response(exc)

    operation_data = InvestmentOperationService.serialize(operation)
    return _compat_success(
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
    try:
        service = InvestmentOperationService(user_id)
        service.delete_operation(investment_id, operation_id)
    except InvestmentOperationError as exc:
        return _operation_error_response(exc)

    return _compat_success(
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
    try:
        service = InvestmentOperationService(user_id)
        summary = service.get_summary(investment_id)
    except InvestmentOperationError as exc:
        return _operation_error_response(exc)

    return _compat_success(
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
    try:
        service = InvestmentOperationService(user_id)
        position = service.get_position(investment_id)
    except InvestmentOperationError as exc:
        return _operation_error_response(exc)

    return _compat_success(
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
    try:
        service = InvestmentOperationService(user_id)
        result = service.get_invested_amount_by_date(investment_id, date)
    except InvestmentOperationError as exc:
        return _operation_error_response(exc)

    return _compat_success(
        legacy_payload={"result": result},
        status_code=200,
        message="Valor investido no período retornado com sucesso",
        data={"result": result},
    )


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
    service = PortfolioValuationService(user_id)
    payload = service.get_portfolio_current_valuation()
    return _compat_success(
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

    raw_start_date = request.args.get("startDate")
    raw_final_date = request.args.get("finalDate")

    try:
        start_date = _parse_optional_query_date(raw_start_date, "startDate")
        final_date = _parse_optional_query_date(raw_final_date, "finalDate")
    except ValueError as exc:
        return _compat_error(
            legacy_payload={"error": str(exc)},
            status_code=400,
            message=str(exc),
            error_code="VALIDATION_ERROR",
        )

    service = PortfolioHistoryService(user_id)
    try:
        payload = service.get_history(start_date=start_date, end_date=final_date)
    except ValueError as exc:
        return _compat_error(
            legacy_payload={"error": str(exc)},
            status_code=400,
            message=str(exc),
            error_code="VALIDATION_ERROR",
        )

    return _compat_success(
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
    service = PortfolioValuationService(user_id)
    try:
        valuation = service.get_investment_current_valuation(investment_id)
    except InvestmentOperationError as exc:
        return _operation_error_response(exc)

    return _compat_success(
        legacy_payload={"valuation": valuation},
        status_code=200,
        message="Valorização do investimento retornada com sucesso",
        data={"valuation": valuation},
    )


# PUT /wallet/<uuid:investment_id> - Atualizar investimento existente
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro inesperado ao atualizar investimento.")
        return _compat_error(
            legacy_payload={"error": "Erro interno"},
            status_code=500,
            message="Erro interno",
            error_code="INTERNAL_ERROR",
        )


# DELETE /wallet/<uuid:investment_id> - Deletar investimento existente
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao deletar investimento.")
        return _compat_error(
            legacy_payload={"error": "Erro ao deletar investimento"},
            status_code=500,
            message="Erro ao deletar investimento",
            error_code="INTERNAL_ERROR",
        )
