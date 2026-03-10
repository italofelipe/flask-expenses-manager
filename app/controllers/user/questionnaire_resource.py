from __future__ import annotations

from typing import Tuple
from uuid import UUID

from flask import Response, jsonify, request
from flask.views import MethodView
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from app.application.services.user_profile_service import (
    evaluate_questionnaire,
    get_questionnaire,
)
from app.extensions.database import db
from app.models.user import User
from app.schemas.user_schemas import (
    QuestionnaireAnswerSchema,
    QuestionnaireResultSchema,
)


class UserQuestionnaireResource(MethodView):
    @jwt_required()  # type: ignore[untyped-decorator]
    def get(self) -> Response | Tuple[Response, int]:
        questions = get_questionnaire()
        return jsonify({"questions": questions}), 200

    @jwt_required()  # type: ignore[untyped-decorator]
    def post(self) -> Response | Tuple[Response, int]:
        user_id = get_jwt_identity()
        user = db.session.get(User, UUID(str(user_id)))
        if not user:
            return jsonify({"error": "User not found"}), 404

        schema = QuestionnaireAnswerSchema()
        try:
            data = schema.load(request.json or {})
        except ValidationError as err:
            return jsonify({"errors": err.messages}), 422

        answers = data.get("answers", [])
        result = evaluate_questionnaire(user, answers)

        if "error" in result:
            return jsonify({"error": result["error"]}), 400

        db.session.commit()

        result_schema = QuestionnaireResultSchema()
        return jsonify(result_schema.dump(result)), 200
