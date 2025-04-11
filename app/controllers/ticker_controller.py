from typing import no_type_check

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from app.extensions.database import db
from app.models.user_ticker import UserTicker
from app.schemas.user_ticker_schema import UserTickerSchema

ticker_bp = Blueprint("ticker", __name__, url_prefix="/wallet")


@no_type_check
@jwt_required()
def get_wallet() -> Response:
    user_id = get_jwt_identity()
    tickers = UserTicker.query.filter_by(user_id=user_id).all()
    schema = UserTickerSchema(many=True)
    return jsonify({"tickers": schema.dump(tickers), "count": len(tickers)}), 200


@no_type_check
@jwt_required()
def add_ticker() -> Response:
    user_id = get_jwt_identity()
    data = request.get_json()
    schema = UserTickerSchema()

    try:
        validated_data = schema.load(data)
    except ValidationError as err:
        return jsonify({"error": "Dados inválidos", "messages": err.messages}), 400

    exists = UserTicker.query.filter_by(
        user_id=user_id, symbol=validated_data["symbol"].upper()
    ).first()
    if exists:
        return jsonify({"error": "Ticker já adicionado"}), 400

    try:
        ticker = UserTicker(
            symbol=validated_data["symbol"].upper(),
            quantity=validated_data["quantity"],
            type=validated_data.get("type"),
            user_id=user_id,
        )
        db.session.add(ticker)
        db.session.commit()
        return jsonify(schema.dump(ticker)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao adicionar ticker", "message": str(e)}), 400


@no_type_check
@jwt_required()
def delete_ticker(symbol: str) -> Response:
    user_id = get_jwt_identity()
    ticker = UserTicker.query.filter_by(user_id=user_id, symbol=symbol.upper()).first()
    if not ticker:
        return jsonify({"error": "Ticker não encontrado"}), 404
    db.session.delete(ticker)
    db.session.commit()
    return jsonify({"message": "Ticker removido com sucesso"}), 200
