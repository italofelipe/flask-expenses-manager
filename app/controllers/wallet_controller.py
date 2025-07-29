from typing import Any, Dict
from uuid import UUID

from flask import Blueprint, request
from flask_apispec import doc
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError
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
        return {"message": "Ativo cadastrado com sucesso"}, 201
    except Exception as e:
        db.session.rollback()
        import traceback

        print("Erro inesperado:", traceback.format_exc())
        print("Tipo:", type(e), "| Args:", e.args)
        return {"error": "Internal Server Error", "message": str(e)}, 500
