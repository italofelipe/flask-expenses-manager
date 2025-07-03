from datetime import timedelta
from typing import Any

from flask import Blueprint, Response, abort, jsonify, make_response
from flask_apispec import doc, marshal_with, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import (
    create_access_token,
    get_jti,
    get_jwt_identity,
    jwt_required,
)
from webargs import ValidationError as WebargsValidationError
from webargs.flaskparser import parser
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions.database import db
from app.models.user import User
from app.schemas.auth_schema import AuthSchema, AuthSuccessResponseSchema
from app.schemas.error_schema import ErrorResponseSchema
from app.schemas.user_schemas import UserRegistrationSchema

JSON_MIMETYPE = "application/json"

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


class RegisterResource(MethodResource):
    @doc(
        description="Cria um novo usuário no sistema",
        tags=["Autenticação"],
        responses={
            201: {"description": "Usuário criado com sucesso"},
            400: {"description": "Erro de validação"},
            409: {"description": "Email já registrado"},
            500: {"description": "Erro interno do servidor"},
        },
    )  # type: ignore[misc]
    @use_kwargs(UserRegistrationSchema, location="json")  # type: ignore[misc]
    def post(self, **validated_data: Any) -> Response:
        if User.query.filter_by(email=validated_data["email"]).first():
            return Response(
                jsonify(
                    {"message": "Email already registered", "data": None}
                ).get_data(),
                status=409,
                mimetype=JSON_MIMETYPE,
            )

        try:
            hashed_password = generate_password_hash(validated_data["password"])
            user = User(
                name=validated_data["name"],
                email=validated_data["email"],
                password=hashed_password,
            )
            db.session.add(user)
            db.session.flush()
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
                mimetype=JSON_MIMETYPE,
            )
        except Exception as e:
            db.session.rollback()
            return Response(
                jsonify(
                    {"message": "Failed to create user", "error": str(e)}
                ).get_data(),
                status=500,
                mimetype=JSON_MIMETYPE,
            )


class AuthResource(MethodResource):
    @doc(
        description="Autenticação de usuário (email ou nome devem ser fornecidos)",
        tags=["Autenticação"],
        requestBody={
            "required": True,
            "content": {
                "application/json": {
                    "schema": AuthSchema,
                    "example": {
                        "email": "email@email.com",
                        "password": "<YOUR_PASSWORD>",
                    },
                }
            },
        },
        responses={
            200: {"description": "Login realizado com sucesso"},
            400: {"description": "Credenciais ausentes"},
            401: {"description": "Credenciais inválidas"},
            500: {"description": "Erro interno ao efetuar login"},
        },
    )  # type: ignore[misc]
    @use_kwargs(AuthSchema, location="json")  # type: ignore[misc]
    @marshal_with(AuthSuccessResponseSchema, code=200)  # type: ignore[misc]
    @marshal_with(ErrorResponseSchema, code=400)  # type: ignore[misc]
    @marshal_with(ErrorResponseSchema, code=401)  # type: ignore[misc]
    @marshal_with(ErrorResponseSchema, code=500)  # type: ignore[misc]
    def post(self, **kwargs: Any) -> Response:
        email = kwargs.get("email")
        name = kwargs.get("name")
        password = kwargs.get("password")

        if not password or not (email or name):
            return Response(
                jsonify({"message": "Missing credentials"}).get_data(),
                status=400,
                mimetype=JSON_MIMETYPE,
            )

        user = (
            User.query.filter_by(email=email).first()
            if email
            else User.query.filter_by(name=name).first()
        )

        if not user or not check_password_hash(user.password, password):
            return Response(
                jsonify({"message": "Invalid credentials"}).get_data(),
                status=401,
                mimetype=JSON_MIMETYPE,
            )

        try:
            token = create_access_token(
                identity=str(user.id), expires_delta=timedelta(hours=1)
            )
            jti = get_jti(token)
            if user.current_jti != jti:
                user.current_jti = jti
                db.session.commit()
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
                mimetype=JSON_MIMETYPE,
            )
        except Exception as e:
            return Response(
                jsonify({"message": "Login failed", "error": str(e)}).get_data(),
                status=500,
                mimetype=JSON_MIMETYPE,
            )


class LogoutResource(MethodResource):
    @doc(
        description="Revoga o token JWT atual (logout do usuário)",
        tags=["Autenticação"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Logout realizado com sucesso"},
        },
    )  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def post(self) -> Response:
        identity = get_jwt_identity()
        user = User.query.get(identity)
        if user:
            user.current_jti = None
            db.session.commit()
        return Response(
            jsonify({"message": "Logout successful"}).get_data(),
            status=200,
            mimetype=JSON_MIMETYPE,
        )


auth_bp.add_url_rule(
    "/register", view_func=RegisterResource.as_view("registerresource")
)
auth_bp.add_url_rule("/login", view_func=AuthResource.as_view("authresource"))
auth_bp.add_url_rule("/logout", view_func=LogoutResource.as_view("logoutresource"))


# ----------------------------------------------------------------------
# Global Webargs validation error handler
# ----------------------------------------------------------------------
@parser.error_handler
def handle_webargs_error(  # type: ignore[override]
    err: WebargsValidationError,
    req,
    schema=None,
    *,
    error_status_code=None,
    error_headers=None,
    **kwargs,
):
    """
    Converte erros de validação (422) do Webargs/Marshmallow em uma
    resposta JSON 400 mais amigável para o cliente.
    """
    error_message = "Validation error"
    if "password" in err.messages:
        error_message = (
            "Senha inválida: não atende aos critérios mínimos de segurança "
            "(mín. 10 caracteres, 1 letra maiúscula, 1 número e 1 símbolo)."
        )

    resp = make_response(
        jsonify({"message": error_message, "errors": err.messages}), 400
    )
    abort(resp)  # Levanta HTTPException para Webargs/Flask
