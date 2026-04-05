from marshmallow import Schema, fields, validate

CREDIT_CARD_BRANDS = ("visa", "mastercard", "elo", "hipercard", "amex", "other")


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
    brand = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.OneOf(CREDIT_CARD_BRANDS),
        metadata={
            "description": "Bandeira do cartão",
            "example": "mastercard",
        },
    )
    limit_amount = fields.Decimal(
        required=False,
        allow_none=True,
        as_string=False,
        metadata={
            "description": "Limite do cartão",
            "example": 5000.00,
        },
    )
    closing_day = fields.Int(
        required=False,
        allow_none=True,
        validate=validate.Range(min=1, max=28),
        metadata={
            "description": "Dia de fechamento da fatura (1-28)",
            "example": 20,
        },
    )
    due_day = fields.Int(
        required=False,
        allow_none=True,
        validate=validate.Range(min=1, max=28),
        metadata={
            "description": "Dia de vencimento da fatura (1-28)",
            "example": 5,
        },
    )
    last_four_digits = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(equal=4),
        metadata={
            "description": "Últimos 4 dígitos do cartão",
            "example": "1234",
        },
    )


class CreditCardResponseSchema(Schema):
    """Schema para resposta de cartões de crédito"""

    id = fields.UUID(metadata={"description": "ID único do cartão"})
    user_id = fields.UUID(metadata={"description": "ID do usuário"})
    name = fields.Str(metadata={"description": "Nome do cartão"})
    brand = fields.Str(allow_none=True, metadata={"description": "Bandeira do cartão"})
    limit_amount = fields.Float(
        allow_none=True, metadata={"description": "Limite do cartão"}
    )
    closing_day = fields.Int(
        allow_none=True, metadata={"description": "Dia de fechamento"}
    )
    due_day = fields.Int(allow_none=True, metadata={"description": "Dia de vencimento"})
    last_four_digits = fields.Str(
        allow_none=True, metadata={"description": "Últimos 4 dígitos"}
    )


class CreditCardListSchema(Schema):
    """Schema para listagem de cartões de crédito"""

    credit_cards = fields.List(fields.Nested(CreditCardResponseSchema))
    total = fields.Int(metadata={"description": "Total de cartões"})
    page = fields.Int(metadata={"description": "Página atual"})
    per_page = fields.Int(metadata={"description": "Itens por página"})
