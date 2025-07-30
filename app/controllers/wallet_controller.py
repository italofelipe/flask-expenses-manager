from typing import Any, Dict
from uuid import UUID

from flask import Blueprint, request
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError, fields
from requests import get  # type: ignore[import-untyped]

from app.extensions.database import db
from app.models.wallet import Wallet
from app.schemas.wallet_schema import WalletSchema
from config import Config

wallet_bp = Blueprint("wallet", __name__, url_prefix="/wallet")


@wallet_bp.route("", methods=["POST"])
@doc(
    description=(
        "Adiciona um novo item à carteira do usuário.\n\n"
        "Você pode informar um valor fixo (como R$1000,00 em poupança) ou um ativo com ticker.\n\n"
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
def add_wallet_entry() -> tuple[dict[str, str], int]:
    """Adiciona um novo item à carteira do usuário com validação de ticker."""
    user_id: UUID = UUID(get_jwt_identity())
    data: Dict[str, Any] = request.get_json()

    # Normalização entre ticker e value
    has_ticker = data.get("ticker") is not None
    if has_ticker:
        data["value"] = None
    else:
        data["ticker"] = None

    schema = WalletSchema()

    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return {"error": "Dados inválidos", "messages": str(err.messages)}, 400

    ticker: str | None = validated_data.get("ticker")
    estimated_value_on_create_date: float | None = None

    if ticker:
        ticker = ticker.upper()

        config = Config()
        brapi_resp = get(
            f"https://brapi.dev/api/quote/{ticker}",
            headers={"Authorization": f"Bearer {config.BRAPI_KEY}"},
        )
        if brapi_resp.status_code != 200 or not brapi_resp.json().get("results"):
            return {"error": f"Ticker inválido: {ticker}"}, 400

        validated_data["ticker"] = ticker
        market_price = brapi_resp.json()["results"][0]["regularMarketPrice"]
        estimated_value_on_create_date = (
            float(market_price) * validated_data["quantity"]
        )
    # Se não houver ticker, estimated_value_on_create_date permanece None

    try:
        new_wallet = Wallet(
            user_id=user_id,
            name=validated_data["name"],
            value=validated_data["value"],
            estimated_value_on_create_date=estimated_value_on_create_date,
            ticker=validated_data.get("ticker"),
            quantity=validated_data.get("quantity"),
            register_date=validated_data["register_date"],
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
        return {
            "message": "Ativo cadastrado com sucesso",
            "investment": investment_data,
        }, 201
    except Exception as e:
        db.session.rollback()
        import traceback

        print("Erro inesperado:", traceback.format_exc())
        print("Tipo:", type(e), "| Args:", e.args)
        return {"error": "Internal Server Error", "message": str(e)}, 500


# GET /wallet - Listar investimentos do usuário com paginação
@wallet_bp.route("", methods=["GET"])
@doc(
    description="Lista os investimentos cadastrados na carteira com paginação.",
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
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
    return {
        "items": items,
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }, 200


# PUT /wallet/<uuid:investment_id> - Atualizar investimento existente
from flask import jsonify  # (caso precise de jsonify, mas manter padrão de retorno)


@wallet_bp.route("/<uuid:investment_id>", methods=["PUT"])
@doc(
    description="Atualiza um investimento existente da carteira do usuário.",
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={"investment_id": {"description": "ID do investimento"}},
    responses={
        200: {"description": "Investimento atualizado com sucesso"},
        400: {"description": "Dados inválidos"},
        401: {"description": "Token inválido"},
        404: {"description": "Investimento não encontrado"},
    },
)
@jwt_required()  # type: ignore[misc]
def update_wallet_entry(investment_id: UUID) -> tuple[dict[str, Any], int]:
    """Atualiza um investimento existente (pertencente ao usuário autenticado)."""
    user_id: UUID = UUID(get_jwt_identity())
    data: Dict[str, Any] = request.get_json()
    print("DATA", data)
    print("INVESTMENT_ID", investment_id)
    print("USER_ID", user_id)
    # (Removido: Normalização entre ticker e value conforme regras de criação)

    schema = WalletSchema(partial=True)
    try:
        validated_data = schema.load(data, partial=True)
    except ValidationError as err:
        return {"error": "Dados inválidos", "messages": str(err.messages)}, 400

    # Busca o investimento pelo ID como string
    investment = Wallet.query.filter_by(id=str(investment_id)).first()
    # Verifica se o usuário é o dono do investimento
    if investment and str(investment.user_id) != str(user_id):
        return {"error": "Você não tem permissão para editar este investimento."}, 403
    if not investment:
        return {"error": "Investimento não encontrado"}, 404

    # Guarda valores antigos para comparação
    old_quantity = investment.quantity
    old_ticker = investment.ticker
    old_value = investment.value

    # Aplica apenas os campos enviados
    for field, value in validated_data.items():
        setattr(investment, field, value)

    # Recalcula estimated_value_on_create_date se quantity ou ticker mudou
    new_quantity = investment.quantity
    new_ticker = investment.ticker
    new_value = investment.value

    if new_quantity != old_quantity or new_ticker != old_ticker:
        if new_ticker:
            # busca preço atual via BRAPI
            config = Config()
            resp = get(
                f"https://brapi.dev/api/quote/{new_ticker.upper()}",
                headers={"Authorization": f"Bearer {config.BRAPI_KEY}"},
            )
            if resp.status_code == 200 and resp.json().get("results"):
                price = resp.json()["results"][0]["regularMarketPrice"]
                investment.estimated_value_on_create_date = float(price) * float(
                    new_quantity
                )
        elif new_value is not None:
            # recalc para valor fixo
            investment.estimated_value_on_create_date = float(new_value) * float(
                new_quantity
            )

    try:
        db.session.commit()
        schema = WalletSchema()
        investment_data = schema.dump(investment)
        # Omite campos conforme tipo de investimento
        if investment_data.get("ticker") is None:
            # hardcoded: omit ticker, quantity, and estimated value
            investment_data.pop("estimated_value_on_create_date", None)
            investment_data.pop("ticker", None)
            investment_data.pop("quantity", None)
        else:
            # ticker: omit value
            investment_data.pop("value", None)
        return {
            "message": "Investimento atualizado com sucesso",
            "investment": investment_data,
        }, 200

    except Exception as e:
        db.session.rollback()
        import traceback

        print("Erro inesperado:", traceback.format_exc())
        return {"error": "Erro interno", "message": str(e)}, 500


# DELETE /wallet/<uuid:investment_id> - Deletar investimento existente
@wallet_bp.route("/<uuid:investment_id>", methods=["DELETE"])
@doc(
    description="Deleta um investimento da carteira do usuário autenticado.",
    tags=["Wallet"],
    security=[{"BearerAuth": []}],
    params={"investment_id": {"description": "ID do investimento"}},
    responses={
        200: {"description": "Investimento deletado com sucesso"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão para deletar"},
        404: {"description": "Investimento não encontrado"},
    },
)  # type: ignore[misc]
@jwt_required()  # type: ignore[misc]
def delete_wallet_entry(investment_id: UUID) -> tuple[dict[str, str], int]:
    """Deleta um investimento existente (pertencente ao usuário autenticado)."""
    user_id: UUID = UUID(get_jwt_identity())
    # Busca o investimento pelo ID como string
    investment = Wallet.query.filter_by(id=str(investment_id)).first()
    if not investment:
        return {"error": "Investimento não encontrado"}, 404
    # Verifica permissão de usuário
    if str(investment.user_id) != str(user_id):
        return {"error": "Você não tem permissão para deletar este investimento."}, 403
    try:
        db.session.delete(investment)
        db.session.commit()
        return {"message": "Investimento deletado com sucesso"}, 200
    except Exception as e:
        db.session.rollback()
        return {"error": "Erro ao deletar investimento", "message": str(e)}, 500
