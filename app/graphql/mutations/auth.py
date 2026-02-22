from __future__ import annotations

from datetime import timedelta
from typing import Any, NoReturn, cast

import graphene
from flask_jwt_extended import create_access_token, get_jti
from graphql import GraphQLError
from marshmallow import ValidationError
from werkzeug.security import generate_password_hash

from app.application.services.auth_security_policy_service import (
    get_auth_security_policy,
)
from app.application.services.password_verification_service import (
    verify_password_with_timing_protection,
)
from app.application.services.user_profile_service import update_user_profile
from app.extensions.database import db
from app.graphql.auth import get_current_user_required
from app.graphql.errors import (
    GRAPHQL_ERROR_CODE_AUTH_BACKEND_UNAVAILABLE,
    GRAPHQL_ERROR_CODE_CONFLICT,
    GRAPHQL_ERROR_CODE_TOO_MANY_ATTEMPTS,
    GRAPHQL_ERROR_CODE_UNAUTHORIZED,
    GRAPHQL_ERROR_CODE_VALIDATION,
    build_public_graphql_error,
)
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


def _public_graphql_error(message: str, *, code: str) -> GraphQLError:
    return build_public_graphql_error(message, code=code)


def _raise_auth_backend_unavailable(exc: Exception) -> NoReturn:
    raise build_public_graphql_error(
        AUTH_BACKEND_UNAVAILABLE_MESSAGE,
        code=GRAPHQL_ERROR_CODE_AUTH_BACKEND_UNAVAILABLE,
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
        investor_profile = graphene.String()

    Output = AuthPayloadType

    def mutate(
        self,
        info: graphene.ResolveInfo,
        name: str,
        email: str,
        password: str,
        investor_profile: str | None = None,
    ) -> AuthPayloadType:
        auth_policy = get_auth_security_policy()
        registration_schema = UserRegistrationSchema()
        try:
            validated = registration_schema.load(
                {
                    "name": name,
                    "email": email,
                    "password": password,
                    "investor_profile": investor_profile,
                }
            )
        except ValidationError as exc:
            messages = exc.messages
            if isinstance(messages, dict):
                flat = "; ".join(
                    f"{field}: {', '.join(str(item) for item in errors)}"
                    for field, errors in messages.items()
                )
                raise _public_graphql_error(
                    flat or "Dados inválidos para registro.",
                    code=GRAPHQL_ERROR_CODE_VALIDATION,
                ) from exc
            raise _public_graphql_error(
                "Dados inválidos para registro.",
                code=GRAPHQL_ERROR_CODE_VALIDATION,
            ) from exc

        duplicate_user = User.query.filter_by(email=validated["email"]).first()
        if duplicate_user:
            if auth_policy.registration.conceal_conflict:
                return AuthPayloadType(
                    message=auth_policy.registration.accepted_message,
                )
            raise _public_graphql_error(
                auth_policy.registration.conflict_message,
                code=GRAPHQL_ERROR_CODE_CONFLICT,
            )

        user = User(
            name=validated["name"],
            email=validated["email"],
            password=generate_password_hash(validated["password"]),
            investor_profile=validated.get("investor_profile"),
        )
        db.session.add(user)
        db.session.commit()
        if auth_policy.registration.conceal_conflict:
            return AuthPayloadType(
                message=auth_policy.registration.accepted_message,
            )
        return AuthPayloadType(
            message=auth_policy.registration.created_message,
            user=UserType(**_user_to_graphql_payload(user)),
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
            raise _public_graphql_error(
                "Missing credentials",
                code=GRAPHQL_ERROR_CODE_VALIDATION,
            )

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
            raise build_public_graphql_error(
                "Too many login attempts. Try again later.",
                code=GRAPHQL_ERROR_CODE_TOO_MANY_ATTEMPTS,
                retry_after_seconds=retry_after,
            )

        password_hash = user.password if user is not None else None
        is_valid_password = verify_password_with_timing_protection(
            password_hash=password_hash,
            plain_password=password,
        )
        if not user or not is_valid_password:
            _guard_register_failure_or_raise(
                login_guard=login_guard,
                login_context=login_context,
            )
            raise _public_graphql_error(
                "Invalid credentials",
                code=GRAPHQL_ERROR_CODE_UNAUTHORIZED,
            )

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
        monthly_income_net = graphene.Float()
        net_worth = graphene.Float()
        monthly_expenses = graphene.Float()
        initial_investment = graphene.Float()
        monthly_investment = graphene.Float()
        investment_goal_date = graphene.String()
        state_uf = graphene.String()
        occupation = graphene.String()
        investor_profile = graphene.String()
        financial_objectives = graphene.String()

    user = graphene.Field(UserType, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, **kwargs: Any
    ) -> "UpdateUserProfileMutation":
        user = get_current_user_required()
        payload = dict(kwargs)
        if (
            "monthly_income" not in payload
            and "monthly_income_net" in payload
            and payload.get("monthly_income_net") is not None
        ):
            payload["monthly_income"] = payload["monthly_income_net"]
        result = update_user_profile(user, payload)
        if result["error"]:
            raise _public_graphql_error(
                str(result["error"]),
                code=GRAPHQL_ERROR_CODE_VALIDATION,
            )
        errors = user.validate_profile_data()
        if errors:
            raise _public_graphql_error(
                f"Erro de validação: {errors}",
                code=GRAPHQL_ERROR_CODE_VALIDATION,
            )
        db.session.commit()
        return UpdateUserProfileMutation(
            user=UserType(**_user_to_graphql_payload(user))
        )
