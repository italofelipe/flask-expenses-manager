from datetime import timedelta
from typing import Any, TypedDict, cast

from flask import Blueprint, Response, jsonify
from flask_apispec import doc, marshal_with, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import (
    create_access_token,
    get_jti,
    get_jwt_identity,
    jwt_required,
)
from marshmallow import ValidationError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions.database import db
from app.models import User
from app.schemas.auth_schema import AuthSchema, AuthSuccessResponseSchema
from app.schemas.error_schema import ErrorResponseSchema
from app.schemas.user_schemas import UserRegistrationSchema

JSON_MIMETYPE = "application/json"

login_bp = Blueprint("auth", __name__, url_prefix="/auth")


class ValidatedUserData(TypedDict):
    name: str
    email: str
    password: str


class RegisterResource(MethodResource):
    @doc(description="Registro de novo usuário", tags=["Autenticação"])  # type: ignore[misc]
    @use_kwargs(UserRegistrationSchema, location="json")  # type: ignore[misc]
    def post(self, **kwargs: Any) -> Response:
        schema = UserRegistrationSchema()
        try:
            validated_data = cast(ValidatedUserData, schema.load(kwargs))
        except ValidationError as err:
            return Response(
                jsonify(
                    {"message": "Validation error", "errors": err.messages}
                ).get_data(),
                status=400,
                mimetype=JSON_MIMETYPE,
            )

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
        description="Revoga o token JWT atual",
        tags=["Autenticação"],
        security=[{"BearerAuth": []}],
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


login_bp.add_url_rule(
    "/register", view_func=RegisterResource.as_view("registerresource")
)
login_bp.add_url_rule("/login", view_func=AuthResource.as_view("authresource"))
login_bp.add_url_rule("/logout", view_func=LogoutResource.as_view("logoutresource"))
