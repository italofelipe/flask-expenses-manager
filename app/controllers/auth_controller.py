from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Union, cast

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import create_access_token
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions.database import db
from app.models import User

login_bp = Blueprint("login", __name__, url_prefix="/login")


@cast(Callable[..., Response], login_bp.route("/register", methods=["POST"]))
def register() -> Response:
    data = request.get_json()

    # Validação mínima
    required_fields = ["name", "email", "password"]
    if not data or not all(field in data for field in required_fields):
        return Response(
            jsonify({"message": "Missing required fields", "data": None}).get_data(),
            status=400,
            mimetype="application/json",
        )

    try:
        # Verifica se o e-mail já existe
        if User.query.filter_by(email=data["email"]).first():
            return Response(
                jsonify(
                    {"message": "Email already registered", "data": None}
                ).get_data(),
                status=409,
                mimetype="application/json",
            )

        # Criptografa a senha
        hashed_password = generate_password_hash(data["password"])

        # Cria novo usuário
        user = User(
            name=data["name"],
            email=data["email"],
            password=hashed_password,
        )
        db.session.add(user)
        db.session.flush()
        print(user.id)
        db.session.commit()

        return Response(
            jsonify(
                {
                    "message": "User created successfully",
                    "data": {
                        "id": str(user.id),
                        "name": user.name,
                        "email": user.email,
                    },
                }
            ).get_data(),
            status=201,
            mimetype="application/json",
        )

    except Exception as e:
        db.session.rollback()
        return Response(
            jsonify({"message": "Failed to create user", "error": str(e)}).get_data(),
            status=500,
            mimetype="application/json",
        )


@cast(Callable[..., Response], login_bp.route("/auth", methods=["POST"]))
def authenticate() -> Response:
    data = request.get_json()

    if (
        not data
        or not data.get("password")
        or not (data.get("email") or data.get("name"))
    ):
        return Response(
            jsonify({"message": "Missing credentials"}).get_data(),
            status=400,
            mimetype="application/json",
        )
    user = None
    if data.get("email"):
        user = User.query.filter_by(email=data["email"]).first()
    elif data.get("name"):
        user = User.query.filter_by(name=data["name"]).first()

    if not user or not check_password_hash(user.password, data["password"]):
        return Response(
            jsonify({"message": "Invalid credentials"}).get_data(),
            status=401,
            mimetype="application/json",
        )

    try:
        token = create_access_token(
            identity=str(user.id), expires_delta=timedelta(hours=1)
        )

        return Response(
            jsonify(
                {
                    "message": "Login successful",
                    "token": token,
                    "user": {
                        "id": str(user.id),
                        "name": user.name,
                        "email": user.email,
                    },
                }
            ).get_data(),
            status=200,
            mimetype="application/json",
        )

    except Exception as e:
        return Response(
            jsonify({"message": "Login failed", "error": str(e)}).get_data(),
            status=500,
            mimetype="application/json",
        )


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
                        "field": field,
                        "message": (
                            f"Formato inválido para '{field}'. Use 'YYYY-MM-DD'."
                        ),
                    }
            setattr(user, field, value)
    return {"error": False}
