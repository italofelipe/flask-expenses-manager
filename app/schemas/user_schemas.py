from flask_marshmallow import Marshmallow
from marshmallow import Schema, fields, pre_load, validate

from app.schemas.sanitization import sanitize_string_fields

ma = Marshmallow()
USER_FULL_NAME_DESCRIPTION = "Nome completo do usuário"


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

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(data, {"name", "email"})
        if isinstance(sanitized, dict) and isinstance(sanitized.get("email"), str):
            sanitized["email"] = str(sanitized["email"]).lower()
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
        validate=validate.OneOf(["conservador", "explorador", "entusiasta"]),
        metadata={"description": "Perfil do investidor", "example": "conservador"},
    )

    financial_objectives = fields.String(
        metadata={
            "description": "Objetivos financeiros do usuário",
            "example": "Aposentar cedo",
        },
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        return sanitize_string_fields(data, {"gender"})


class UserSchema(Schema):
    """Schema para resposta de dados do usuário"""

    id = fields.UUID(metadata={"description": "ID único do usuário"})
    name = fields.String(metadata={"description": USER_FULL_NAME_DESCRIPTION})
    email = fields.Email(metadata={"description": "Endereço de email do usuário"})
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
        as_string=True,
        metadata={"description": "Investimento inicial"},
    )
    monthly_investment = fields.Decimal(
        as_string=True,
        metadata={"description": "Investimento mensal"},
    )
    investment_goal_date = fields.Date(
        metadata={"description": "Data meta de investimento"}
    )
    state_uf = fields.String(metadata={"description": "Estado (UF) do usuário"})
    occupation = fields.String(metadata={"description": "Profissão do usuário"})
    investor_profile = fields.String(metadata={"description": "Perfil do investidor"})
    financial_objectives = fields.String(
        metadata={"description": "Objetivos financeiros do usuário"}
    )
    created_at = fields.DateTime(metadata={"description": "Data de criação"})
    updated_at = fields.DateTime(metadata={"description": "Data de atualização"})
