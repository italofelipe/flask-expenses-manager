from flask_marshmallow import Marshmallow
from marshmallow import Schema, fields, validate

ma = Marshmallow()


class UserRegistrationSchema(Schema):
    """Schema para registro de novos usuários"""

    name = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=128),
        description="Nome completo do usuário",
        example="João Silva",
    )
    email = fields.Email(
        required=True,
        description="Endereço de email único do usuário",
        example="joao.silva@email.com",
    )
    password = fields.Str(
        required=True,
        load_only=True,
        description=(
            "Senha do usuário (mínimo 10 caracteres, "
            "contendo ao menos uma letra maiúscula, um número e um símbolo)"
        ),
        example="MinhaSenha@123",
        validate=validate.Regexp(
            r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}$",
            error=(
                "A senha deve ter no mínimo 10 caracteres, conter ao menos "
                "uma letra maiúscula, um número e um símbolo."
            ),
        ),
    )


class UserProfileSchema(Schema):
    """Schema para atualização do perfil do usuário"""

    gender = fields.String(
        validate=validate.OneOf(["masculino", "feminino", "outro"]),
        description="Gênero do usuário",
        example="masculino",
    )
    birth_date = fields.Date(description="Data de nascimento", example="1990-05-15")
    monthly_income = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        description="Renda mensal em reais",
        example="5000.00",
    )
    net_worth = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        description="Patrimônio líquido atual",
        example="50000.00",
    )
    monthly_expenses = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        description="Gastos mensais totais",
        example="3000.00",
    )
    initial_investment = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        description="Investimento inicial disponível",
        example="10000.00",
    )
    monthly_investment = fields.Decimal(
        as_string=True,
        validate=validate.Range(min=0),
        description="Valor mensal para investimentos",
        example="1000.00",
    )
    investment_goal_date = fields.Date(
        description="Data meta para atingir objetivo de investimento",
        example="2030-12-31",
    )


class UserSchema(Schema):
    """Schema para resposta de dados do usuário"""

    id = fields.UUID(description="ID único do usuário")
    name = fields.String(description="Nome completo do usuário")
    email = fields.Email(description="Endereço de email do usuário")
    created_at = fields.DateTime(description="Data de criação da conta")
    updated_at = fields.DateTime(description="Data da última atualização")


class UserCompleteSchema(Schema):
    """Schema completo com todos os dados do usuário"""

    id = fields.UUID(description="ID único do usuário")
    name = fields.String(description="Nome completo do usuário")
    email = fields.Email(description="Endereço de email do usuário")
    gender = fields.String(description="Gênero do usuário")
    birth_date = fields.Date(description="Data de nascimento")
    monthly_income = fields.Decimal(as_string=True, description="Renda mensal")
    net_worth = fields.Decimal(as_string=True, description="Patrimônio líquido")
    monthly_expenses = fields.Decimal(as_string=True, description="Gastos mensais")
    initial_investment = fields.Decimal(
        as_string=True, description="Investimento inicial"
    )
    monthly_investment = fields.Decimal(
        as_string=True, description="Investimento mensal"
    )
    investment_goal_date = fields.Date(description="Data meta de investimento")
    created_at = fields.DateTime(description="Data de criação")
    updated_at = fields.DateTime(description="Data de atualização")
