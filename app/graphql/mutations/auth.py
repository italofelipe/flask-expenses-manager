from __future__ import annotations

from datetime import timedelta
from typing import Any, NoReturn, cast

import graphene
from flask_jwt_extended import create_access_token, get_jti
from graphql import GraphQLError
from marshmallow import ValidationError
from werkzeug.security import check_password_hash, generate_password_hash

from app.application.services.auth_security_policy_service import (
    get_auth_security_policy,
)
from app.controllers.user_controller import assign_user_profile_fields
from app.extensions.database import db
from app.graphql.auth import get_current_user_required
from app.graphql.schema_utils import _user_basic_auth_payload, _user_to_graphql_payload
from app.graphql.types import AuthPayloadType, UserType
from app.models.user import User
from app.schemas.user_schemas import UserRegistrationSchema
from app.services.login_attempt_guard_service import (
    LoginAttemptContext,
    LoginAttemptGuardService,
    LoginGuardBackendUnavailableError,
    build_login_attempt_context,
    get_login_attempt_guard,
)

AUTH_BACKEND_UNAVAILABLE_MESSAGE = (
    "Authentication temporarily unavailable. Try again later."
)


def _raise_auth_backend_unavailable(exc: Exception) -> NoReturn:
    raise GraphQLError(
        AUTH_BACKEND_UNAVAILABLE_MESSAGE,
        extensions={"code": "AUTH_BACKEND_UNAVAILABLE", "reason": str(exc)},
    ) from exc


def _guard_check_or_raise(
    *,
    login_guard: LoginAttemptGuardService,
    login_context: LoginAttemptContext,
) -> tuple[bool, int]:
    try:
        return login_guard.check(login_context)
    except LoginGuardBackendUnavailableError as exc:
        _raise_auth_backend_unavailable(exc)


def _guard_register_failure_or_raise(
    *,
    login_guard: LoginAttemptGuardService,
    login_context: LoginAttemptContext,
) -> None:
    try:
        login_guard.register_failure(login_context)
    except LoginGuardBackendUnavailableError as exc:
        _raise_auth_backend_unavailable(exc)


def _guard_register_success_or_raise(
    *,
    login_guard: LoginAttemptGuardService,
    login_context: LoginAttemptContext,
) -> None:
    try:
        login_guard.register_success(login_context)
    except LoginGuardBackendUnavailableError as exc:
        _raise_auth_backend_unavailable(exc)


class RegisterUserMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    Output = AuthPayloadType

    def mutate(
        self, info: graphene.ResolveInfo, name: str, email: str, password: str
    ) -> AuthPayloadType:
        auth_policy = get_auth_security_policy()
        registration_schema = UserRegistrationSchema()
        try:
            validated = registration_schema.load(
                {"name": name, "email": email, "password": password}
            )
        except ValidationError as exc:
            messages = exc.messages
            if isinstance(messages, dict):
                flat = "; ".join(
                    f"{field}: {', '.join(str(item) for item in errors)}"
                    for field, errors in messages.items()
                )
                raise GraphQLError(flat or "Dados inválidos para registro.") from exc
            raise GraphQLError("Dados inválidos para registro.") from exc

        duplicate_user = User.query.filter_by(email=validated["email"]).first()
        if duplicate_user:
            if auth_policy.registration.conceal_conflict:
                return AuthPayloadType(
                    message=auth_policy.registration.accepted_message,
                )
            raise GraphQLError(auth_policy.registration.conflict_message)

        user = User(
            name=validated["name"],
            email=validated["email"],
            password=generate_password_hash(validated["password"]),
        )
        db.session.add(user)
        db.session.commit()
        if auth_policy.registration.conceal_conflict:
            return AuthPayloadType(
                message=auth_policy.registration.accepted_message,
            )
        return AuthPayloadType(
            message=auth_policy.registration.created_message,
            user=UserType(**_user_basic_auth_payload(user)),
        )


class LoginMutation(graphene.Mutation):
    class Arguments:
        email = graphene.String()
        name = graphene.String()
        password = graphene.String(required=True)

    Output = AuthPayloadType

    def mutate(
        self,
        info: graphene.ResolveInfo,
        password: str,
        email: str | None = None,
        name: str | None = None,
    ) -> AuthPayloadType:
        auth_policy = get_auth_security_policy()
        if not (email or name):
            raise GraphQLError("Missing credentials")

        principal = str(email or name or "")
        user = (
            User.query.filter_by(email=email).first()
            if email
            else User.query.filter_by(name=name).first()
        )
        request_obj = cast(dict[str, Any], info.context).get("request")
        headers = request_obj.headers if request_obj is not None else {}
        login_context = build_login_attempt_context(
            principal=principal,
            remote_addr=(
                getattr(request_obj, "remote_addr", None)
                if request_obj is not None
                else None
            ),
            user_agent=headers.get("User-Agent") if headers else None,
            forwarded_for=headers.get("X-Forwarded-For") if headers else None,
            real_ip=headers.get("X-Real-IP") if headers else None,
            known_principal=(
                user is not None and auth_policy.login_guard.expose_known_principal
            ),
        )
        login_guard = get_login_attempt_guard()
        allowed, retry_after = _guard_check_or_raise(
            login_guard=login_guard,
            login_context=login_context,
        )
        if not allowed:
            raise GraphQLError(
                "Too many login attempts. Try again later.",
                extensions={
                    "code": "TOO_MANY_ATTEMPTS",
                    "retry_after_seconds": retry_after,
                },
            )

        if not user or not check_password_hash(user.password, password):
            _guard_register_failure_or_raise(
                login_guard=login_guard,
                login_context=login_context,
            )
            raise GraphQLError("Invalid credentials")

        _guard_register_success_or_raise(
            login_guard=login_guard,
            login_context=login_context,
        )
        token = create_access_token(
            identity=str(user.id), expires_delta=timedelta(hours=1)
        )
        jti = get_jti(token)
        if user.current_jti != jti:
            user.current_jti = jti
            db.session.commit()
        return AuthPayloadType(
            message="Login successful",
            token=token,
            user=UserType(**_user_basic_auth_payload(user)),
        )


class LogoutMutation(graphene.Mutation):
    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(self, info: graphene.ResolveInfo) -> "LogoutMutation":
        user = get_current_user_required()
        user.current_jti = None
        db.session.commit()
        return LogoutMutation(ok=True, message="Logout successful")


class UpdateUserProfileMutation(graphene.Mutation):
    class Arguments:
        gender = graphene.String()
        birth_date = graphene.String()
        monthly_income = graphene.Float()
        net_worth = graphene.Float()
        monthly_expenses = graphene.Float()
        initial_investment = graphene.Float()
        monthly_investment = graphene.Float()
        investment_goal_date = graphene.String()

    user = graphene.Field(UserType, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, **kwargs: Any
    ) -> "UpdateUserProfileMutation":
        user = get_current_user_required()
        result = assign_user_profile_fields(user, kwargs)
        if result["error"]:
            raise GraphQLError(str(result["message"]))
        errors = user.validate_profile_data()
        if errors:
            raise GraphQLError(f"Erro de validação: {errors}")
        db.session.commit()
        return UpdateUserProfileMutation(
            user=UserType(**_user_to_graphql_payload(user))
        )
