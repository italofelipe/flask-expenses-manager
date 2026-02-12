from marshmallow import Schema, fields, validate


class CreditCardSchema(Schema):
    """Schema para criação e atualização de cartões de crédito"""

    id = fields.UUID(
        dump_only=True,
        metadata={"description": "ID único do cartão (gerado automaticamente)"},
    )
    user_id = fields.UUID(
        required=False,
        metadata={"description": "ID do usuário proprietário do cartão"},
    )
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        metadata={
            "description": "Nome do cartão de crédito",
            "example": "Nubank Mastercard",
        },
    )


class CreditCardResponseSchema(Schema):
    """Schema para resposta de cartões de crédito"""

    id = fields.UUID(metadata={"description": "ID único do cartão"})
    user_id = fields.UUID(metadata={"description": "ID do usuário"})
    name = fields.Str(metadata={"description": "Nome do cartão"})


class CreditCardListSchema(Schema):
    """Schema para listagem de cartões de crédito"""

    credit_cards = fields.List(fields.Nested(CreditCardResponseSchema))
    total = fields.Int(metadata={"description": "Total de cartões"})
    page = fields.Int(metadata={"description": "Página atual"})
    per_page = fields.Int(metadata={"description": "Itens por página"})
