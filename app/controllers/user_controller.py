from datetime import datetime
from typing import Any, Callable, Dict, Union, cast
from uuid import UUID

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions.database import db
from app.models import User

user_bp = Blueprint("user", __name__, url_prefix="/user")


def assign_user_profile_fields(
    user: User, data: Dict[str, Any]
) -> Dict[str, Union[str, bool]]:
    date_fields = ["birth_date", "investment_goal_date"]
    for field in [
        "gender",
        "birth_date",
        "monthly_income",
        "net_worth",
        "monthly_expenses",
        "initial_investment",
        "monthly_investment",
        "investment_goal_date",
    ]:
        if field in data:
            value = data[field]
            if field in date_fields and isinstance(value, str):
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return {
                        "error": True,
                        "message": (
                            f"Formato inválido para '{field}'. Use 'YYYY-MM-DD'."
                        ),
                    }
            setattr(user, field, value)
    return {"error": False}


@cast(Callable[..., Response], user_bp.route("/profile", methods=["PUT"]))
@cast(Callable[..., Response], jwt_required())
def update_profile() -> Response:
    user_id = UUID(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return Response(
            jsonify({"message": "Usuário não encontrado"}).get_data(),
            status=404,
            mimetype="application/json",
        )

    data = request.get_json()

    result = assign_user_profile_fields(user, data)
    if result["error"]:
        return Response(
            jsonify({"message": result["message"]}).get_data(),
            status=400,
            mimetype="application/json",
        )

    # Validação de dados
    errors = user.validate_profile_data()
    if errors:
        return Response(
            jsonify({"message": "Erro de validação", "errors": errors}).get_data(),
            status=400,
            mimetype="application/json",
        )

    try:
        db.session.commit()
        return Response(
            jsonify(
                {
                    "message": "Perfil atualizado com sucesso",
                    "data": {
                        "id": str(user.id),
                        "name": user.name,
                        "email": user.email,
                        "gender": user.gender,
                        "birth_date": (
                            str(user.birth_date) if user.birth_date else None
                        ),
                        "monthly_income": (
                            float(user.monthly_income) if user.monthly_income else None
                        ),
                        "net_worth": (
                            float(user.net_worth) if user.net_worth else None
                        ),
                        "monthly_expenses": (
                            float(user.monthly_expenses)
                            if user.monthly_expenses
                            else None
                        ),
                        "initial_investment": (
                            float(user.initial_investment)
                            if user.initial_investment
                            else None
                        ),
                        "monthly_investment": (
                            float(user.monthly_investment)
                            if user.monthly_investment
                            else None
                        ),
                        "investment_goal_date": (
                            str(user.investment_goal_date)
                            if user.investment_goal_date
                            else None
                        ),
                    },
                }
            ).get_data(),
            status=200,
            mimetype="application/json",
        )
    except Exception as e:
        return Response(
            jsonify(
                {"message": "Erro ao atualizar perfil", "error": str(e)}
            ).get_data(),
            status=500,
            mimetype="application/json",
        )


@cast(Callable[..., Response], user_bp.route("/me", methods=["GET"]))
@cast(Callable[..., Response], jwt_required())
def get_profile() -> Response:
    user_id = UUID(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return Response(
            jsonify({"message": "Usuário não encontrado"}).get_data(),
            status=404,
            mimetype="application/json",
        )

    return Response(
        jsonify(
            {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "gender": user.gender,
                "birth_date": (str(user.birth_date) if user.birth_date else None),
                "monthly_income": (
                    float(user.monthly_income) if user.monthly_income else None
                ),
                "net_worth": (float(user.net_worth) if user.net_worth else None),
                "monthly_expenses": (
                    float(user.monthly_expenses) if user.monthly_expenses else None
                ),
                "initial_investment": (
                    float(user.initial_investment) if user.initial_investment else None
                ),
                "monthly_investment": (
                    float(user.monthly_investment) if user.monthly_investment else None
                ),
                "investment_goal_date": (
                    str(user.investment_goal_date)
                    if user.investment_goal_date
                    else None
                ),
            }
        ).get_data(),
        status=200,
        mimetype="application/json",
    )


@cast(Callable[..., Response], user_bp.route("/debug-token", methods=["GET"]))
@cast(Callable[..., Response], jwt_required())
def debug_token() -> Response:
    user_id = UUID(get_jwt_identity())
    return Response(
        jsonify({"message": "Token válido", "user_id": str(user_id)}).get_data(),
        status=200,
        mimetype="application/json",
    )
