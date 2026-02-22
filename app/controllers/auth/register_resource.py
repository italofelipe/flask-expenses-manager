# mypy: disable-error-code=misc

from __future__ import annotations

from typing import Any

from flask import Response, current_app
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource

from app.extensions.database import db
from app.models.user import User
from app.schemas.user_schemas import UserRegistrationSchema

from .contracts import compat_error, compat_success, registration_ack_payload
from .dependencies import get_auth_dependencies


class RegisterResource(MethodResource):
    @doc(
        description="Cria um novo usuário no sistema",
        tags=["Autenticação"],
        params={
            "X-API-Contract": {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            }
        },
        responses={
            201: {"description": "Usuário criado com sucesso"},
            400: {"description": "Erro de validação"},
            409: {"description": "Email já registrado"},
            500: {"description": "Erro interno do servidor"},
        },
    )
    @use_kwargs(UserRegistrationSchema, location="json")
    def post(self, **validated_data: Any) -> Response:
        dependencies = get_auth_dependencies()
        auth_policy = dependencies.get_auth_security_policy()
        duplicate_user = dependencies.find_user_by_email(validated_data["email"])
        if duplicate_user:
            if auth_policy.registration.conceal_conflict:
                return compat_success(
                    legacy_payload=registration_ack_payload(
                        auth_policy.registration.accepted_message
                    ),
                    status_code=201,
                    message=auth_policy.registration.accepted_message,
                    data={},
                )
            return compat_error(
                legacy_payload={
                    "message": auth_policy.registration.conflict_message,
                    "data": None,
                },
                status_code=409,
                message=auth_policy.registration.conflict_message,
                error_code="CONFLICT",
            )

        try:
            hashed_password = dependencies.hash_password(validated_data["password"])
            user = User(
                name=validated_data["name"],
                email=validated_data["email"],
                password=hashed_password,
                investor_profile=validated_data.get("investor_profile"),
            )
            db.session.add(user)
            db.session.flush()
            db.session.commit()

            if auth_policy.registration.conceal_conflict:
                return compat_success(
                    legacy_payload=registration_ack_payload(
                        auth_policy.registration.accepted_message
                    ),
                    status_code=201,
                    message=auth_policy.registration.accepted_message,
                    data={},
                )

            user_data = {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
            }
            return compat_success(
                legacy_payload={
                    "message": auth_policy.registration.created_message,
                    "data": user_data,
                },
                status_code=201,
                message=auth_policy.registration.created_message,
                data={"user": user_data},
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to create user.")
            return compat_error(
                legacy_payload={"message": "Failed to create user"},
                status_code=500,
                message="Failed to create user",
                error_code="INTERNAL_ERROR",
            )
