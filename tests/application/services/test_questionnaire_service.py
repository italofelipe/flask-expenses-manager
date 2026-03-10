"""Unit tests for the questionnaire functions in user_profile_service.

These tests run WITHOUT Flask app context — no DB, no HTTP client.
They test the pure functions and immutability guarantees directly.
"""

from __future__ import annotations

from app.application.services.user_profile_service import (
    QUESTIONNAIRE,
    QUESTIONNAIRE_OPTION_MAX_POINTS,
    QUESTIONNAIRE_OPTION_MIN_POINTS,
    QUESTIONNAIRE_SIZE,
    _UserQuizTarget,
    calculate_profile,
    evaluate_questionnaire,
    get_questionnaire,
)

# ---------------------------------------------------------------------------
# calculate_profile — pure function tests
# ---------------------------------------------------------------------------


class TestCalculateProfile:
    def test_conservador_boundary_low(self) -> None:
        """Score = 5 (mínimo possível) → conservador."""
        result = calculate_profile([1, 1, 1, 1, 1])
        assert result["suggested_profile"] == "conservador"
        assert result["score"] == 5

    def test_conservador_boundary_high(self) -> None:
        """Score = 7 (limite superior do conservador) → conservador."""
        result = calculate_profile([1, 1, 2, 2, 1])  # 1+1+2+2+1 = 7
        assert result["suggested_profile"] == "conservador"
        assert result["score"] == 7

    def test_explorador_boundary_low(self) -> None:
        """Score = 8 (limite inferior do explorador) → explorador."""
        result = calculate_profile([1, 1, 2, 2, 2])  # 1+1+2+2+2 = 8
        assert result["suggested_profile"] == "explorador"
        assert result["score"] == 8

    def test_explorador_midpoint(self) -> None:
        """Score = 10 (centro do explorador) → explorador."""
        result = calculate_profile([2, 2, 2, 2, 2])
        assert result["suggested_profile"] == "explorador"
        assert result["score"] == 10

    def test_explorador_boundary_high(self) -> None:
        """Score = 11 (limite superior do explorador) → explorador."""
        result = calculate_profile([2, 2, 2, 2, 3])  # 2+2+2+2+3 = 11
        assert result["suggested_profile"] == "explorador"
        assert result["score"] == 11

    def test_entusiasta_boundary_low(self) -> None:
        """Score = 12 (limite inferior do entusiasta) → entusiasta."""
        result = calculate_profile([2, 2, 2, 3, 3])  # 2+2+2+3+3 = 12
        assert result["suggested_profile"] == "entusiasta"
        assert result["score"] == 12

    def test_entusiasta_boundary_high(self) -> None:
        """Score = 15 (máximo possível) → entusiasta."""
        result = calculate_profile([3, 3, 3, 3, 3])
        assert result["suggested_profile"] == "entusiasta"
        assert result["score"] == 15

    def test_returns_questionnaire_result_typed_dict(self) -> None:
        """O retorno deve satisfazer o TypedDict QuestionnaireResult."""
        result = calculate_profile([2, 2, 2, 2, 2])
        assert isinstance(result, dict)
        assert "suggested_profile" in result
        assert "score" in result
        assert isinstance(result["suggested_profile"], str)
        assert isinstance(result["score"], int)

    def test_is_pure_same_input_same_output(self) -> None:
        """Mesma entrada → mesma saída (determinístico, sem estado)."""
        r1 = calculate_profile([1, 2, 3, 1, 2])
        r2 = calculate_profile([1, 2, 3, 1, 2])
        assert r1 == r2

    def test_no_side_effects_on_module_state(self) -> None:
        """Chamadas a calculate_profile não alteram QUESTIONNAIRE."""
        original_len = len(QUESTIONNAIRE)
        calculate_profile([3, 3, 3, 3, 3])
        assert len(QUESTIONNAIRE) == original_len


# ---------------------------------------------------------------------------
# get_questionnaire — immutability tests
# ---------------------------------------------------------------------------


class TestGetQuestionnaire:
    def test_returns_correct_number_of_questions(self) -> None:
        """Deve retornar QUESTIONNAIRE_SIZE perguntas."""
        questions = get_questionnaire()
        assert len(questions) == QUESTIONNAIRE_SIZE

    def test_each_question_has_required_fields(self) -> None:
        """Cada pergunta deve ter id, text e options."""
        for q in get_questionnaire():
            assert "id" in q
            assert "text" in q
            assert "options" in q

    def test_option_points_within_valid_range(self) -> None:
        """Todos os pontos das opções devem estar em [min, max].

        Este teste teria falhado com o bug original max=4 vs dados reais max=3.
        """
        lo, hi = QUESTIONNAIRE_OPTION_MIN_POINTS, QUESTIONNAIRE_OPTION_MAX_POINTS
        for question in get_questionnaire():
            for option in question["options"]:
                assert lo <= option["points"] <= hi, (
                    f"Opção '{option['text']}' tem points={option['points']}"
                    f" fora do intervalo [{lo}, {hi}]"
                )

    def test_returns_deep_copy_not_original(self) -> None:
        """get_questionnaire() NÃO deve retornar a lista original QUESTIONNAIRE."""
        q = get_questionnaire()
        assert q is not QUESTIONNAIRE, (
            "Retornou referência ao objeto original — mutação possível"
        )

    def test_two_calls_return_independent_objects(self) -> None:
        """Chamadas distintas retornam objetos independentes."""
        q1 = get_questionnaire()
        q2 = get_questionnaire()
        assert q1 is not q2

    def test_mutation_of_return_does_not_affect_questionnaire(self) -> None:
        """Mutação do retorno NÃO deve alterar o QUESTIONNAIRE canônico."""
        original_text = QUESTIONNAIRE[0]["text"]
        q = get_questionnaire()
        q[0]["text"] = "MUTADO"
        assert QUESTIONNAIRE[0]["text"] == original_text, (
            "get_questionnaire() retornou referência mutável ao QUESTIONNAIRE original"
        )


# ---------------------------------------------------------------------------
# evaluate_questionnaire — protocol + side-effect tests
# ---------------------------------------------------------------------------


class _MockUser:
    """Minimal in-memory mock satisfying the _UserQuizTarget Protocol."""

    investor_profile_suggested: str | None = None
    profile_quiz_score: int | None = None


class TestEvaluateQuestionnaire:
    def test_valid_answers_mutates_user_and_returns_result(self) -> None:
        """Respostas válidas → persiste no user e retorna QuestionnaireResult."""
        user = _MockUser()
        result = evaluate_questionnaire(user, [3, 3, 3, 3, 3])

        assert isinstance(result, dict)
        assert result.get("suggested_profile") == "entusiasta"
        assert result.get("score") == 15
        # Side effects applied:
        assert user.investor_profile_suggested == "entusiasta"
        assert user.profile_quiz_score == 15

    def test_wrong_count_returns_error_dict(self) -> None:
        """Número errado de respostas → dict de erro (sem mutação do user)."""
        user = _MockUser()
        result = evaluate_questionnaire(user, [1, 1, 1])

        assert "error" in result
        # User not mutated on validation failure:
        assert user.investor_profile_suggested is None
        assert user.profile_quiz_score is None

    def test_mock_user_satisfies_protocol(self) -> None:
        """Confirma que _MockUser satisfaz o Protocol _UserQuizTarget."""
        assert isinstance(_MockUser(), _UserQuizTarget)

    def test_result_score_matches_sum_of_answers(self) -> None:
        """O score retornado deve ser a soma exata das respostas."""
        user = _MockUser()
        answers = [1, 2, 3, 2, 1]
        result = evaluate_questionnaire(user, answers)

        assert "error" not in result
        assert result["score"] == sum(answers)
