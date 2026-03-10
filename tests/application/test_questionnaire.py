from app.application.services.user_profile_service import evaluate_questionnaire
from app.models.user import User


def test_evaluate_questionnaire_conservador() -> None:
    user = User()
    answers = [1, 1, 1, 1, 1]
    result = evaluate_questionnaire(user, answers)
    assert result["score"] == 5
    assert result["suggested_profile"] == "conservador"
    assert user.investor_profile_suggested == "conservador"
    assert user.profile_quiz_score == 5


def test_evaluate_questionnaire_explorador() -> None:
    user = User()
    answers = [2, 2, 2, 2, 2]
    result = evaluate_questionnaire(user, answers)
    assert result["score"] == 10
    assert result["suggested_profile"] == "explorador"
    assert user.investor_profile_suggested == "explorador"
    assert user.profile_quiz_score == 10


def test_evaluate_questionnaire_entusiasta() -> None:
    user = User()
    answers = [3, 3, 3, 3, 3]
    result = evaluate_questionnaire(user, answers)
    assert result["score"] == 15
    assert result["suggested_profile"] == "entusiasta"
    assert user.investor_profile_suggested == "entusiasta"
    assert user.profile_quiz_score == 15


def test_evaluate_questionnaire_invalid_length() -> None:
    user = User()
    answers = [1, 2, 3]
    result = evaluate_questionnaire(user, answers)
    assert "error" in result
