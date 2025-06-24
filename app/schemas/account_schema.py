from marshmallow import Schema, fields, validate


class AccountSchema(Schema):
    """Schema para criação e atualização de contas bancárias"""

    id = fields.UUID(
        dump_only=True, description="ID único da conta (gerado automaticamente)"
    )
    user_id = fields.UUID(
        required=False, description="ID do usuário proprietário da conta"
    )
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        description="Nome da conta bancária",
        example="Conta Corrente Nubank",
    )


class AccountResponseSchema(Schema):
    """Schema para resposta de contas bancárias"""

    id = fields.UUID(description="ID único da conta")
    user_id = fields.UUID(description="ID do usuário")
    name = fields.Str(description="Nome da conta")


class AccountListSchema(Schema):
    """Schema para listagem de contas bancárias"""

    accounts = fields.List(fields.Nested(AccountResponseSchema))
    total = fields.Int(description="Total de contas")
    page = fields.Int(description="Página atual")
    per_page = fields.Int(description="Itens por página")
