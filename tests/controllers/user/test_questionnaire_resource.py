"""Integration tests for UserQuestionnaireResource.

Covers GET /user/profile/questionnaire (fetch questions)
and  POST /user/profile/questionnaire (submit answers → investor profile).

Auth pattern: _register_and_login creates a fresh user per test so
each test is fully isolated and does NOT rely on shared fixtures or
session state from other tests.

Schema boundary tests verify that the fixed constraints (max=3, equal=5)
are correctly enforced — these would have caught the original max=4 bug.
"""

from __future__ import annotations

import uuid

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _register_and_login(client) -> str:
    """Register a new unique user and return its JWT access token."""
    suffix = uuid.uuid4().hex[:8]
    email = f"quiz-{suffix}@email.com"
    password = "StrongPass@123"

    register = client.post(
        "/auth/register",
        json={"name": f"quiz-{suffix}", "email": email, "password": password},
    )
    assert register.status_code == 201, register.get_json()

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.get_json()
    return login.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /user/profile/questionnaire
# ---------------------------------------------------------------------------


class TestGetQuestionnaire:
    def test_returns_200_with_five_questions(self, client) -> None:
        """Authenticated GET deve retornar a lista completa de 5 perguntas."""
        token = _register_and_login(client)
        response = client.get("/user/profile/questionnaire", headers=_auth(token))

        assert response.status_code == 200
        data = response.get_json()
        assert "questions" in data
        assert len(data["questions"]) == 5

    def test_each_question_has_required_fields(self, client) -> None:
        """Cada pergunta deve ter id, text e options."""
        token = _register_and_login(client)
        response = client.get("/user/profile/questionnaire", headers=_auth(token))

        for question in response.get_json()["questions"]:
            assert "id" in question
            assert "text" in question
            assert "options" in question
            assert len(question["options"]) > 0

    def test_questionnaire_option_points_within_valid_range(self, client) -> None:
        """Todos os pontos das opções devem estar no intervalo [1, 3] (sem max=4)."""
        from app.application.services.user_profile_service import (
            QUESTIONNAIRE_OPTION_MAX_POINTS,
            QUESTIONNAIRE_OPTION_MIN_POINTS,
        )

        token = _register_and_login(client)
        response = client.get("/user/profile/questionnaire", headers=_auth(token))

        for question in response.get_json()["questions"]:
            for option in question["options"]:
                assert (
                    QUESTIONNAIRE_OPTION_MIN_POINTS
                    <= option["points"]
                    <= QUESTIONNAIRE_OPTION_MAX_POINTS
                ), f"Opção {option} tem pontos fora do intervalo permitido"

    def test_returns_401_without_token(self, client) -> None:
        """GET sem autenticação deve retornar 401."""
        response = client.get("/user/profile/questionnaire")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /user/profile/questionnaire
# ---------------------------------------------------------------------------


class TestPostQuestionnaire:
    def test_conservador_profile(self, client) -> None:
        """5 respostas baixas (score=5) → perfil conservador."""
        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [1, 1, 1, 1, 1]},
            headers=_auth(token),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["suggested_profile"] == "conservador"
        assert data["score"] == 5

    def test_explorador_profile(self, client) -> None:
        """5 respostas médias (score=10) → perfil explorador."""
        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [2, 2, 2, 2, 2]},
            headers=_auth(token),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["suggested_profile"] == "explorador"
        assert data["score"] == 10

    def test_entusiasta_profile(self, client) -> None:
        """5 respostas altas (score=15) → perfil entusiasta."""
        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [3, 3, 3, 3, 3]},
            headers=_auth(token),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["suggested_profile"] == "entusiasta"
        assert data["score"] == 15

    def test_mixed_answers_score_and_profile(self, client) -> None:
        """Respostas mistas (score=9) devem resultar em explorador."""
        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [2, 1, 2, 2, 2]},
            headers=_auth(token),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["score"] == 9
        assert data["suggested_profile"] == "explorador"

    def test_wrong_answer_count_returns_422(self, client) -> None:
        """Número errado de respostas (6 em vez de 5) → 422 (schema: equal=5).

        Com a correção do schema (Length(equal=5)), 6 respostas são rejeitadas
        na camada de validação (422) antes de chegar ao service layer.
        Falha rápida na borda, não no domínio.
        """
        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [1, 1, 1, 1, 1, 1]},
            headers=_auth(token),
        )

        assert response.status_code == 422
        assert "errors" in response.get_json()

    def test_missing_answers_field_returns_422(self, client) -> None:
        """Payload sem o campo 'answers' → 422 da validação do schema."""
        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={},
            headers=_auth(token),
        )

        assert response.status_code == 422

    def test_too_few_answers_returns_422(self, client) -> None:
        """Menos de 5 respostas → 422 (schema: validate.Length(min=5))."""
        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [1, 2, 3]},
            headers=_auth(token),
        )

        assert response.status_code == 422

    def test_returns_401_without_token(self, client) -> None:
        """POST sem autenticação deve retornar 401."""
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [1, 1, 1, 1, 1]},
        )

        assert response.status_code == 401

    def test_answer_value_exceeds_max_returns_422(self, client) -> None:
        """Resposta com pontos acima do máximo (4 > max=3) → 422.

        Este teste garante que o bug original (max=4 no schema) não regride.
        O valor 4 deve ser rejeitado pela validação.
        """
        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [1, 1, 1, 1, 4]},  # 4 > QUESTIONNAIRE_OPTION_MAX_POINTS
            headers=_auth(token),
        )

        assert response.status_code == 422
        body = response.get_json()
        assert "errors" in body

    def test_answer_value_below_min_returns_422(self, client) -> None:
        """Resposta com pontos abaixo do mínimo (0 < min=1) → 422."""
        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [0, 1, 1, 1, 1]},  # 0 < QUESTIONNAIRE_OPTION_MIN_POINTS
            headers=_auth(token),
        )

        assert response.status_code == 422
        body = response.get_json()
        assert "errors" in body

    def test_exactly_five_answers_required(self, client) -> None:
        """A lista de respostas deve ter exatamente 5 itens (não mais, não menos)."""
        token = _register_and_login(client)

        # 4 respostas → 422
        response_short = client.post(
            "/user/profile/questionnaire",
            json={"answers": [1, 1, 1, 1]},
            headers=_auth(token),
        )
        assert response_short.status_code == 422

        # 6 respostas — marshmallow rejeita com equal=5 (não chega no service)
        response_long = client.post(
            "/user/profile/questionnaire",
            json={"answers": [1, 1, 1, 1, 1, 1]},
            headers=_auth(token),
        )
        assert response_long.status_code == 422

    def test_profile_persisted_after_submission(self, client, app) -> None:
        """O perfil sugerido deve ser persistido no model do usuário após o POST."""
        from uuid import UUID

        from flask_jwt_extended import decode_token

        from app.extensions.database import db
        from app.models.user import User

        token = _register_and_login(client)
        response = client.post(
            "/user/profile/questionnaire",
            json={"answers": [3, 3, 3, 3, 3]},
            headers=_auth(token),
        )
        assert response.status_code == 200

        decoded = decode_token(token)
        user_id = UUID(str(decoded["sub"]))

        with app.app_context():
            user = db.session.get(User, user_id)
            assert user is not None
            assert user.investor_profile_suggested == "entusiasta"
            assert user.profile_quiz_score == 15
