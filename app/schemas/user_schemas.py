from flask_marshmallow import Marshmallow
from marshmallow import Schema, fields, pre_load, validate

from app.application.services.user_profile_service import (
    INVESTOR_PROFILE_CHOICES,
    QUESTIONNAIRE_OPTION_MAX_POINTS,
    QUESTIONNAIRE_OPTION_MIN_POINTS,
    QUESTIONNAIRE_SIZE,
)
from app.schemas.sanitization import sanitize_string_fields

ma = Marshmallow()
USER_FULL_NAME_DESCRIPTION = "Nome completo do usuário"
INVESTOR_PROFILE_SUGGESTED_DESCRIPTION = "Perfil de investidor sugerido"
PROFILE_QUIZ_SCORE_DESCRIPTION = "Pontuação do quiz de perfil"
TAXONOMY_VERSION_DESCRIPTION = "Versão da taxonomia"


class UserRegistrationSchema(Schema):
    """Schema para registro de novos usuários"""

    name = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=128),
        metadata={"description": USER_FULL_NAME_DESCRIPTION, "example": "João Silva"},
    )
    email = fields.Email(
        required=True,
        metadata={
            "description": "Endereço de email único do usuário",
            "example": "joao.silva@email.com",
        },
    )
    password = fields.Str(
        required=True,
        load_only=True,
        metadata={
            "description": (
                "Senha do usuário (mínimo 10 caracteres, "
                "contendo ao menos uma letra maiúscula, um número e um símbolo)"
            ),
            "example": "MinhaSenha@123",
        },
        validate=validate.Regexp(
            r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}$",
            error=(
                "A senha deve ter no mínimo 10 caracteres, conter ao menos "
                "uma letra maiúscula, um número e um símbolo."
            ),
        ),
    )
    investor_profile = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(INVESTOR_PROFILE_CHOICES),
        metadata={
            "description": "Perfil do investidor auto declarado",
            "example": "conservador",
        },
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(data, {"name", "email", "investor_profile"})
        if isinstance(sanitized, dict) and isinstance(sanitized.get("email"), str):
            sanitized["email"] = str(sanitized["email"]).lower()
        if isinstance(sanitized, dict) and isinstance(
            sanitized.get("investor_profile"), str
        ):
            sanitized["investor_profile"] = str(sanitized["investor_profile"]).lower()
        return sanitized


class UserProfileSchema(Schema):
    """Schema para atualização do perfil do usuário"""

    gender = fields.String(
        validate=validate.OneOf(["masculino", "feminino", "outro"]),
        metadata={"description": "Gênero do usuário", "example": "masculino"},
    )
    birth_date = fields.Date(
        metadata={"description": "Data de nascimento", "example": "1990-05-15"},
    )
    monthly_income = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        metadata={"description": "Renda mensal em reais", "example": "5000.00"},
    )
    monthly_income_net = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        metadata={
            "description": "Renda líquida mensal em reais",
            "example": "5000.00",
        },
    )
    net_worth = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        metadata={"description": "Patrimônio líquido atual", "example": "50000.00"},
    )
    monthly_expenses = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        metadata={"description": "Gastos mensais totais", "example": "3000.00"},
    )
    initial_investment = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        metadata={
            "description": "Investimento inicial disponível",
            "example": "10000.00",
        },
    )
    monthly_investment = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        metadata={
            "description": "Valor mensal para investimentos",
            "example": "1000.00",
        },
    )
    investment_goal_date = fields.Date(
        metadata={
            "description": "Data meta para atingir objetivo de investimento",
            "example": "2030-12-31",
        },
    )

    state_uf = fields.String(
        validate=validate.Length(equal=2),
        metadata={"description": "Estado (UF) do usuário", "example": "SP"},
    )

    occupation = fields.String(
        validate=validate.Length(max=128),
        metadata={
            "description": "Profissão do usuário",
            "example": "Engenheiro de Software",
        },
    )

    investor_profile = fields.String(
        validate=validate.OneOf(INVESTOR_PROFILE_CHOICES),
        metadata={"description": "Perfil do investidor", "example": "conservador"},
    )

    investor_profile_suggested = fields.String(
        allow_none=True,
        validate=validate.Length(max=32),
        metadata={
            "description": INVESTOR_PROFILE_SUGGESTED_DESCRIPTION,
            "example": "explorador",
        },
    )

    profile_quiz_score = fields.Integer(
        allow_none=True,
        validate=validate.Range(min=0),
        metadata={"description": PROFILE_QUIZ_SCORE_DESCRIPTION, "example": 85},
    )

    taxonomy_version = fields.String(
        allow_none=True,
        validate=validate.Length(max=16),
        metadata={"description": TAXONOMY_VERSION_DESCRIPTION, "example": "v1.0"},
    )

    financial_objectives = fields.String(
        metadata={
            "description": "Objetivos financeiros do usuário",
            "example": "Aposentar cedo",
        },
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(
            data, {"gender", "investor_profile", "investor_profile_suggested"}
        )
        if isinstance(sanitized, dict):
            if isinstance(sanitized.get("state_uf"), str):
                sanitized["state_uf"] = str(sanitized["state_uf"]).upper()
            if (
                "monthly_income" not in sanitized
                and "monthly_income_net" in sanitized
                and sanitized.get("monthly_income_net") is not None
            ):
                sanitized["monthly_income"] = sanitized["monthly_income_net"]
            if isinstance(sanitized.get("investor_profile"), str):
                sanitized["investor_profile"] = str(
                    sanitized["investor_profile"]
                ).lower()
            if isinstance(sanitized.get("investor_profile_suggested"), str):
                sanitized["investor_profile_suggested"] = str(
                    sanitized["investor_profile_suggested"]
                ).lower()
        return sanitized


class UserSchema(Schema):
    """Schema para resposta de dados do usuário"""

    id = fields.UUID(metadata={"description": "ID único do usuário"})
    name = fields.String(metadata={"description": USER_FULL_NAME_DESCRIPTION})
    email = fields.Email(metadata={"description": "Endereço de email do usuário"})
    investor_profile_suggested = fields.String(
        metadata={"description": INVESTOR_PROFILE_SUGGESTED_DESCRIPTION}
    )
    profile_quiz_score = fields.Integer(
        metadata={"description": PROFILE_QUIZ_SCORE_DESCRIPTION}
    )
    taxonomy_version = fields.String(
        metadata={"description": TAXONOMY_VERSION_DESCRIPTION}
    )
    created_at = fields.DateTime(metadata={"description": "Data de criação da conta"})
    updated_at = fields.DateTime(metadata={"description": "Data da última atualização"})


class UserCompleteSchema(Schema):
    """Schema completo com todos os dados do usuário"""

    id = fields.UUID(metadata={"description": "ID único do usuário"})
    name = fields.String(metadata={"description": USER_FULL_NAME_DESCRIPTION})
    email = fields.Email(metadata={"description": "Endereço de email do usuário"})
    gender = fields.String(metadata={"description": "Gênero do usuário"})
    birth_date = fields.Date(metadata={"description": "Data de nascimento"})
    monthly_income = fields.Decimal(
        as_string=True, metadata={"description": "Renda mensal"}
    )
    monthly_income_net = fields.Decimal(
        as_string=True, metadata={"description": "Renda líquida mensal"}
    )
    net_worth = fields.Decimal(
        as_string=True, metadata={"description": "Patrimônio líquido"}
    )
    monthly_expenses = fields.Decimal(
        as_string=True, metadata={"description": "Gastos mensais"}
    )
    initial_investment = fields.Decimal(
        as_string=True, metadata={"description": "Investimento inicial"}
    )
    monthly_investment = fields.Decimal(
        as_string=True, metadata={"description": "Investimento mensal"}
    )
    investment_goal_date = fields.Date(
        metadata={"description": "Data meta de investimento"}
    )
    state_uf = fields.String(metadata={"description": "Estado (UF) do usuário"})
    occupation = fields.String(metadata={"description": "Profissão do usuário"})
    investor_profile = fields.String(metadata={"description": "Perfil do investidor"})
    investor_profile_suggested = fields.String(
        metadata={"description": INVESTOR_PROFILE_SUGGESTED_DESCRIPTION}
    )
    profile_quiz_score = fields.Integer(
        metadata={"description": PROFILE_QUIZ_SCORE_DESCRIPTION}
    )
    taxonomy_version = fields.String(
        metadata={"description": TAXONOMY_VERSION_DESCRIPTION}
    )
    financial_objectives = fields.String(
        metadata={"description": "Objetivos financeiros do usuário"}
    )
    created_at = fields.DateTime(metadata={"description": "Data de criação"})
    updated_at = fields.DateTime(metadata={"description": "Data de atualização"})


class QuestionnaireAnswerSchema(Schema):
    """Schema para validar as respostas enviadas no questionário.

    Constraints derivadas dos dados reais do domínio (``user_profile_service``):
    - Cada resposta é o nº de pontos da opção escolhida: mínimo
      ``QUESTIONNAIRE_OPTION_MIN_POINTS`` (1), máximo
      ``QUESTIONNAIRE_OPTION_MAX_POINTS`` (3).
    - A lista deve ter exatamente ``QUESTIONNAIRE_SIZE`` (5) elementos —
      um por pergunta.
    """

    answers = fields.List(
        fields.Integer(
            validate=validate.Range(
                min=QUESTIONNAIRE_OPTION_MIN_POINTS,
                max=QUESTIONNAIRE_OPTION_MAX_POINTS,
                error=(
                    f"Cada resposta deve ser um inteiro entre "
                    f"{QUESTIONNAIRE_OPTION_MIN_POINTS} e "
                    f"{QUESTIONNAIRE_OPTION_MAX_POINTS}."
                ),
            )
        ),
        required=True,
        validate=validate.Length(
            equal=QUESTIONNAIRE_SIZE,
            error=f"O questionário exige exatamente {QUESTIONNAIRE_SIZE} respostas.",
        ),
        metadata={
            "description": (
                f"Lista de {QUESTIONNAIRE_SIZE} respostas — "
                f"pontos da opção escolhida em cada pergunta "
                f"({QUESTIONNAIRE_OPTION_MIN_POINTS}–{QUESTIONNAIRE_OPTION_MAX_POINTS})."
            )
        },
    )


class QuestionnaireResultSchema(Schema):
    """Schema para o retorno do perfil sugerido"""

    suggested_profile = fields.String(
        metadata={
            "description": "Perfil sugerido (conservador, explorador, entusiasta)"
        }
    )
    score = fields.Integer(metadata={"description": "Pontuação total obtida"})


class SalaryIncreaseSimulationRequestSchema(Schema):
    """Schema para requisição de simulação de aumento salarial"""

    base_salary = fields.Decimal(
        required=True,
        validate=validate.Range(min=0),
        metadata={"description": "Salário base atual", "example": "5000.00"},
    )
    base_date = fields.Date(
        required=True,
        metadata={"description": "Data base do salário atual", "example": "2022-01-01"},
    )
    discounts = fields.Decimal(
        required=True,
        validate=validate.Range(min=0),
        metadata={"description": "Descontos aplicáveis", "example": "500.00"},
    )
    target_real_increase = fields.Decimal(
        required=True,
        validate=validate.Range(min=0),
        metadata={"description": "Aumento real desejado (%)", "example": "5.00"},
    )


class SalaryIncreaseSimulationResponseSchema(Schema):
    """Schema para resposta de simulação de aumento salarial"""

    recomposition = fields.Decimal(
        as_string=True,
        metadata={
            "description": "Valor de recomposição da inflação",
            "example": "250.00",
        },
    )
    target = fields.Decimal(
        as_string=True,
        metadata={"description": "Salário alvo calculado", "example": "5500.00"},
    )
