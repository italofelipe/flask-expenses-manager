from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, JWTManager
from app.extensions.database import db
from app.models import User
from datetime import datetime

user_bp = Blueprint("user", __name__, url_prefix="/user")

@user_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Usuário não encontrado"}), 404

    data = request.get_json()

    # Atribui os dados ao usuário
    for field in [
        "gender",
        "birth_date",
        "monthly_income",
        "net_worth",
        "monthly_expenses",
        "initial_investment",
        "monthly_investment",
        "investment_goal_date"
    ]:
        if field in data:
            value = data[field]
            if field in ["birth_date", "investment_goal_date"] and isinstance(value, str):
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return jsonify({
                        "message": f"Formato inválido para '{field}'. Use 'YYYY-MM-DD'."
                    }), 400
            setattr(user, field, value)

    # Validação de dados
    errors = user.validate_profile_data()
    if errors:
        return jsonify({
            "message": "Erro de validação",
            "errors": errors
        }), 400

    try:
        db.session.commit()
        return jsonify({
            "message": "Perfil atualizado com sucesso",
            "data": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "gender": user.gender,
                "birth_date": str(user.birth_date) if user.birth_date else None,
                "monthly_income": float(user.monthly_income) if user.monthly_income else None,
                "net_worth": float(user.net_worth) if user.net_worth else None,
                "monthly_expenses": float(user.monthly_expenses) if user.monthly_expenses else None,
                "initial_investment": float(user.initial_investment) if user.initial_investment else None,
                "monthly_investment": float(user.monthly_investment) if user.monthly_investment else None,
                "investment_goal_date": str(user.investment_goal_date) if user.investment_goal_date else None,
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "message": "Erro ao atualizar perfil",
            "error": str(e)
        }), 500

@user_bp.route("/me", methods=["GET"])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Usuário não encontrado"}), 404

    return jsonify({
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "gender": user.gender,
        "birth_date": str(user.birth_date) if user.birth_date else None,
        "monthly_income": float(user.monthly_income) if user.monthly_income else None,
        "net_worth": float(user.net_worth) if user.net_worth else None,
        "monthly_expenses": float(user.monthly_expenses) if user.monthly_expenses else None,
        "initial_investment": float(user.initial_investment) if user.initial_investment else None,
        "monthly_investment": float(user.monthly_investment) if user.monthly_investment else None,
        "investment_goal_date": str(user.investment_goal_date) if user.investment_goal_date else None
    }), 200

@user_bp.route("/debug-token", methods=["GET"])
@jwt_required()
def debug_token():
    return jsonify({
        "message": "Token válido",
        "user_id": get_jwt_identity()
    }), 200