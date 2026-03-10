"""Investor profile questionnaire controller.

Provides two HTTP endpoints:

- ``GET /user/profile/questionnaire``  — returns the 5 questions (auth required).
- ``POST /user/profile/questionnaire`` — submits answers, classifies investor
  profile and persists the result on the authenticated user (auth required).

Design notes
------------
- Uses ``MethodResource`` (flask-apispec) instead of the plain ``MethodView``
  to integrate with OpenAPI/Swagger documentation generation — consistent with
  all other controllers in this package.
- Authentication uses the project-standard ``get_active_auth_context()`` +
  ``validate_user_token()`` pair, which enforces JTI-based revocation checks
  (a plain ``db.session.get()`` call would silently allow revoked tokens).
- The service layer (``evaluate_questionnaire``) mutates the user entity in
  place; this controller is responsible for committing the session.
"""

from __future__ import annotations

from typing import Any, cast

from flask import Response
from flask_apispec.views import MethodResource
from marshmallow import ValidationError

from app.application.services.user_profile_service import (
    evaluate_questionnaire,
    get_questionnaire,
)
from app.auth import get_active_auth_context
from app.extensions.database import db
from app.schemas.user_schemas import QuestionnaireAnswerSchema
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_error, compat_success
from .helpers import validate_user_token


class UserQuestionnaireResource(MethodResource):
    @doc(
        description=(
            "Retorna as 5 perguntas do questionário de perfil de investidor.\n\n"
            "Cada pergunta contém 3 opções com pontuações de 1 a 3.\n"
            "Envie os pontos via POST para receber o perfil sugerido."
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Lista de perguntas retornada com sucesso"},
            401: {"description": "Token inválido, expirado ou revogado"},
        },
    )
    @jwt_required()
    def get(self) -> Response:
        """Return the investor profile questionnaire questions."""
        auth_context = get_active_auth_context()
        user_or_response = validate_user_token(auth_context)
        if isinstance(user_or_response, Response):
            return user_or_response

        questions = get_questionnaire()
        return compat_success(
            legacy_payload={"questions": questions},
            status_code=200,
            message="Questionário retornado com sucesso",
            data={"questions": questions},
        )

    @doc(
        description=(
            "Submete as respostas do questionário e classifica"
            " o perfil de investidor.\n\n"
            "Envie exatamente 5 respostas, cada uma com os pontos"
            " da opção escolhida (1–3).\n\n"
            "Perfis possíveis:\n"
            "- **conservador** — score ≤ 7\n"
            "- **explorador**  — score de 8 a 11\n"
            "- **entusiasta**  — score ≥ 12\n\n"
            "O resultado é persistido no perfil do usuário autenticado."
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Perfil sugerido calculado e persistido"},
            400: {"description": "Número de respostas inválido"},
            401: {"description": "Token inválido, expirado ou revogado"},
            422: {"description": "Payload inválido: pontuação ou campo ausente"},
        },
    )
    @jwt_required()
    def post(self) -> Response:
        """Submit questionnaire answers and persist the suggested investor profile."""
        from flask import request

        auth_context = get_active_auth_context()
        user_or_response = validate_user_token(auth_context)
        if isinstance(user_or_response, Response):
            return user_or_response
        user = user_or_response

        schema = QuestionnaireAnswerSchema()
        try:
            data = schema.load(request.json or {})
        except ValidationError as err:
            return compat_error(
                legacy_payload={"errors": err.messages},
                status_code=422,
                message="Dados inválidos",
                error_code="VALIDATION_ERROR",
                details=cast("dict[str, Any]", err.messages),
            )

        answers: list[int] = data.get("answers", [])
        result = evaluate_questionnaire(user, answers)

        if "error" in result:
            error_dict: dict[str, str] = result  # type: ignore[assignment]
            return compat_error(
                legacy_payload={"error": error_dict["error"]},
                status_code=400,
                message=error_dict["error"],
                error_code="INVALID_ANSWER_COUNT",
            )

        db.session.commit()

        return compat_success(
            legacy_payload={
                "suggested_profile": result["suggested_profile"],
                "score": result["score"],
            },
            status_code=200,
            message="Perfil sugerido calculado com sucesso",
            data={
                "suggested_profile": result["suggested_profile"],
                "score": result["score"],
            },
        )
