"""User profile and investor questionnaire service.

This module provides two distinct concerns:

1. **Questionnaire** — the 5-question investor profile quiz.
   - ``get_questionnaire()``      — read-only access to the canonical question list.
   - ``calculate_profile()``      — **pure function**, no side effects.  FastAPI-safe.
   - ``evaluate_questionnaire()`` — orchestrator: validates, calculates and persists.

2. **Profile update** — general-purpose mutable profile fields.
   - ``update_user_profile()``    — applies validated data to the user entity.

FastAPI migration path
----------------------
The service layer is decoupled from Flask via the ``_UserQuizTarget`` Protocol.
To migrate ``evaluate_questionnaire`` to FastAPI:

    result = calculate_profile(answers)          # pure — no changes needed
    await session.execute(
        update(User).where(User.id == user_id)
        .values(investor_profile_suggested=result["suggested_profile"],
                profile_quiz_score=result["score"])
    )
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Protocol, TypedDict, runtime_checkable

# ---------------------------------------------------------------------------
# Domain constants (single source of truth — imported by schemas and tests)
# ---------------------------------------------------------------------------

INVESTOR_PROFILE_CHOICES = ("conservador", "explorador", "entusiasta")
VALID_INVESTOR_PROFILES = set(INVESTOR_PROFILE_CHOICES)

#: Total number of questions in the questionnaire.  Used by the schema to
#: enforce exactly this many answers (``validate.Length(equal=QUESTIONNAIRE_SIZE)``).
QUESTIONNAIRE_SIZE: int = 5

#: Minimum points assignable to a single answer option.
QUESTIONNAIRE_OPTION_MIN_POINTS: int = 1

#: Maximum points assignable to a single answer option.
#: Schema must use this constant — do NOT hardcode 4 (the original bug).
QUESTIONNAIRE_OPTION_MAX_POINTS: int = 3

# Score thresholds — private to this module.  Changing scoring logic only
# requires editing these two lines.
_CONSERVADOR_MAX_SCORE: int = 7  # score ≤ 7  → conservador
_EXPLORADOR_MAX_SCORE: int = 11  # score ≤ 11 → explorador  (else → entusiasta)

_DATE_FIELDS = {"birth_date", "investment_goal_date"}
_PROFILE_MUTABLE_FIELDS = (
    "gender",
    "birth_date",
    "monthly_income",
    "monthly_income_net",
    "net_worth",
    "monthly_expenses",
    "initial_investment",
    "monthly_investment",
    "investment_goal_date",
    "state_uf",
    "occupation",
    "financial_objectives",
    # B11: investor profile suggestion fields (persisted from quiz results)
    "profile_quiz_score",
    "taxonomy_version",
)

# ---------------------------------------------------------------------------
# Typed structures
# ---------------------------------------------------------------------------


class QuestionnaireOption(TypedDict):
    """A single selectable option within a questionnaire question."""

    id: int
    text: str
    points: int


class QuestionnaireQuestion(TypedDict):
    """A single question in the investor profile questionnaire."""

    id: int
    text: str
    options: list[QuestionnaireOption]


class QuestionnaireResult(TypedDict):
    """Return value of ``calculate_profile()``.

    FastAPI-compatible: this is a plain dict subtype, serialisable by both
    ``jsonify()`` (Flask) and ``response_model`` (FastAPI).
    """

    suggested_profile: str
    score: int


# ---------------------------------------------------------------------------
# Protocol — decouples service from SQLAlchemy User model (DIP)
# ---------------------------------------------------------------------------


@runtime_checkable
class _UserQuizTarget(Protocol):
    """Structural contract for any object that can receive quiz results.

    Using ``Protocol`` instead of importing ``app.models.user.User`` directly
    means the service has no hard dependency on SQLAlchemy.  In a FastAPI
    migration, an async-ORM entity or a plain dataclass satisfies this
    contract without any changes to the service code.
    """

    investor_profile_suggested: str | None
    profile_quiz_score: int | None


# ---------------------------------------------------------------------------
# Canonical questionnaire data
# ---------------------------------------------------------------------------

QUESTIONNAIRE: list[QuestionnaireQuestion] = [
    {
        "id": 1,
        "text": "Qual o seu principal objetivo ao investir?",
        "options": [
            {"id": 1, "text": "Preservar meu patrimônio", "points": 1},
            {"id": 2, "text": "Crescimento moderado", "points": 2},
            {"id": 3, "text": "Maximizar a rentabilidade", "points": 3},
        ],
    },
    {
        "id": 2,
        "text": "Como você reagiria a uma queda de 10% nos seus investimentos?",
        "options": [
            {"id": 1, "text": "Venderia tudo", "points": 1},
            {"id": 2, "text": "Manteria e aguardaria", "points": 2},
            {"id": 3, "text": "Compraria mais", "points": 3},
        ],
    },
    {
        "id": 3,
        "text": "Por quanto tempo pretende deixar seu dinheiro investido?",
        "options": [
            {"id": 1, "text": "Menos de 1 ano", "points": 1},
            {"id": 2, "text": "De 1 a 5 anos", "points": 2},
            {"id": 3, "text": "Mais de 5 anos", "points": 3},
        ],
    },
    {
        "id": 4,
        "text": "Qual a sua experiência com investimentos?",
        "options": [
            {"id": 1, "text": "Nenhuma, estou começando", "points": 1},
            {"id": 2, "text": "Conheço o básico (renda fixa)", "points": 2},
            {"id": 3, "text": "Tenho experiência (renda variável)", "points": 3},
        ],
    },
    {
        "id": 5,
        "text": "Qual proporção da sua renda você consegue investir mensalmente?",
        "options": [
            {"id": 1, "text": "Menos de 10%", "points": 1},
            {"id": 2, "text": "Entre 10% e 20%", "points": 2},
            {"id": 3, "text": "Mais de 20%", "points": 3},
        ],
    },
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_questionnaire() -> list[QuestionnaireQuestion]:
    """Return the questionnaire as an independent deep copy.

    Returns a new list on every call.  Callers cannot mutate the canonical
    ``QUESTIONNAIRE`` constant by modifying the returned value.

    Returns:
        A deep copy of ``QUESTIONNAIRE``.
    """
    return copy.deepcopy(QUESTIONNAIRE)


def calculate_profile(answers: list[int]) -> QuestionnaireResult:
    """Map a list of answer scores to an investor profile — **pure function**.

    No I/O, no DB access, no side effects.  Can be called safely from any
    context (Flask, FastAPI, CLI, tests without app context).

    Args:
        answers: List of integer scores, one per question.  Each value must
                 be between ``QUESTIONNAIRE_OPTION_MIN_POINTS`` and
                 ``QUESTIONNAIRE_OPTION_MAX_POINTS`` (validated by the schema
                 before reaching this function).

    Returns:
        ``QuestionnaireResult`` with ``suggested_profile`` and ``score``.

    Note:
        This function does **not** validate ``len(answers)``.  That
        responsibility belongs to the caller (``evaluate_questionnaire`` or
        the schema layer).
    """
    score = sum(answers)

    if score <= _CONSERVADOR_MAX_SCORE:
        suggested = "conservador"
    elif score <= _EXPLORADOR_MAX_SCORE:
        suggested = "explorador"
    else:
        suggested = "entusiasta"

    return QuestionnaireResult(suggested_profile=suggested, score=score)


def evaluate_questionnaire(
    user: _UserQuizTarget,
    answers: list[int],
) -> QuestionnaireResult | dict[str, str]:
    """Validate, classify, and persist the investor profile quiz result.

    This is the primary use-case entry point for the questionnaire feature.
    It delegates the pure classification logic to ``calculate_profile()`` and
    then applies the result to the user entity.

    **Side effects** (explicit):
        Mutates ``user.investor_profile_suggested`` and
        ``user.profile_quiz_score``.  The caller is responsible for
        committing the database session.

    Args:
        user: Any object satisfying ``_UserQuizTarget`` (e.g. the
              SQLAlchemy ``User`` model).  Decoupled via Protocol (DIP).
        answers: List of integer scores, one per question.

    Returns:
        ``QuestionnaireResult`` on success, or ``{"error": str}`` if the
        answer count does not match ``QUESTIONNAIRE_SIZE``.

    FastAPI migration note:
        Call ``calculate_profile(answers)`` directly in the route handler,
        then persist via ``await session.execute(update(User).values(...))``.
    """
    if len(answers) != QUESTIONNAIRE_SIZE:
        return {"error": "Número de respostas inválido."}

    result = calculate_profile(answers)

    # --- Side effects (documented) ---
    user.investor_profile_suggested = result["suggested_profile"]
    user.profile_quiz_score = result["score"]

    return result


# ---------------------------------------------------------------------------
# Profile update helpers (pre-existing, unrelated to the questionnaire)
# ---------------------------------------------------------------------------


def _parse_date(field_name: str, value: Any) -> tuple[Any, str | None]:
    if value is None or not isinstance(value, str):
        return value, None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"Formato inválido para '{field_name}'. Use 'YYYY-MM-DD'."


def _normalize_investor_profile(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return normalized


def _apply_declared_investor_profile(user: Any, data: dict[str, Any]) -> str | None:
    """Apply investor_profile (declared). Returns an error string or None."""
    if "investor_profile" not in data:
        return None
    normalized = _normalize_investor_profile(data["investor_profile"])
    if normalized is None:
        user.investor_profile = None
        return None
    if normalized not in VALID_INVESTOR_PROFILES:
        return f"Perfil do investidor inválido: {data['investor_profile']}"
    user.investor_profile = normalized
    return None


def _apply_suggested_investor_profile(user: Any, data: dict[str, Any]) -> None:
    """Apply investor_profile_suggested (B11 — quiz-derived, any lowercase string)."""
    if "investor_profile_suggested" in data:
        user.investor_profile_suggested = _normalize_investor_profile(
            data["investor_profile_suggested"]
        )


def update_user_profile(user: Any, data: dict[str, Any]) -> dict[str, str | None]:
    error = _apply_declared_investor_profile(user, data)
    if error:
        return {"error": error}

    _apply_suggested_investor_profile(user, data)

    for field in _PROFILE_MUTABLE_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if field in _DATE_FIELDS:
            parsed_value, error = _parse_date(field, value)
            if error:
                return {"error": error}
            value = parsed_value
        if field == "state_uf" and isinstance(value, str):
            value = value.upper()
        if field == "monthly_income_net":
            user.monthly_income_net = value
            continue
        setattr(user, field, value)

    return {"error": None}
