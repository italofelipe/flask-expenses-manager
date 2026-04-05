from marshmallow import Schema, fields, validate

ACCOUNT_TYPES = ("checking", "savings", "investment", "wallet", "other")


class AccountSchema(Schema):
    """Schema para criação e atualização de contas bancárias"""

    id = fields.UUID(
        dump_only=True,
        metadata={"description": "ID único da conta (gerado automaticamente)"},
    )
    user_id = fields.UUID(
        required=False,
        metadata={"description": "ID do usuário proprietário da conta"},
    )
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        metadata={
            "description": "Nome da conta bancária",
            "example": "Conta Corrente Nubank",
        },
    )
    account_type = fields.Str(
        required=False,
        load_default="checking",
        validate=validate.OneOf(ACCOUNT_TYPES),
        metadata={
            "description": "Tipo da conta",
            "example": "checking",
        },
    )
    institution = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=100),
        metadata={
            "description": "Nome da instituição financeira",
            "example": "Nubank",
        },
    )
    initial_balance = fields.Decimal(
        required=False,
        load_default=0,
        as_string=False,
        metadata={
            "description": "Saldo inicial da conta",
            "example": 1000.00,
        },
    )


class AccountResponseSchema(Schema):
    """Schema para resposta de contas bancárias"""

    id = fields.UUID(metadata={"description": "ID único da conta"})
    user_id = fields.UUID(metadata={"description": "ID do usuário"})
    name = fields.Str(metadata={"description": "Nome da conta"})
    account_type = fields.Str(metadata={"description": "Tipo da conta"})
    institution = fields.Str(
        allow_none=True, metadata={"description": "Instituição financeira"}
    )
    initial_balance = fields.Float(metadata={"description": "Saldo inicial"})


class AccountListSchema(Schema):
    """Schema para listagem de contas bancárias"""

    accounts = fields.List(fields.Nested(AccountResponseSchema))
    total = fields.Int(metadata={"description": "Total de contas"})
    page = fields.Int(metadata={"description": "Página atual"})
    per_page = fields.Int(metadata={"description": "Itens por página"})
