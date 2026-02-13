from marshmallow import Schema, fields, validate


class UserTickerSchema(Schema):
    """Schema para criação e atualização de tickers do usuário"""

    id = fields.UUID(
        dump_only=True,
        metadata={"description": "ID único do ticker (gerado automaticamente)"},
    )
    symbol = fields.String(
        required=True,
        validate=validate.Length(min=1, max=10),
        metadata={
            "description": "Símbolo do ativo (ex: PETR4, VALE3)",
            "example": "PETR4",
        },
    )
    quantity = fields.Float(
        required=True,
        validate=validate.Range(min=0.01),
        metadata={
            "description": "Quantidade de ações/ativos possuídos",
            "example": 100.0,
        },
    )
    type = fields.String(
        required=False,
        validate=validate.OneOf(["stock", "fii", "etf", "bond", "crypto", "other"]),
        metadata={"description": "Tipo do ativo", "example": "stock"},
    )
    user_id = fields.UUID(
        dump_only=True,
        metadata={"description": "ID do usuário proprietário do ticker"},
    )


class UserTickerResponseSchema(Schema):
    """Schema para resposta de tickers do usuário"""

    id = fields.UUID(metadata={"description": "ID único do ticker"})
    symbol = fields.String(metadata={"description": "Símbolo do ativo"})
    quantity = fields.Float(metadata={"description": "Quantidade possuída"})
    type = fields.String(metadata={"description": "Tipo do ativo"})
    user_id = fields.UUID(metadata={"description": "ID do usuário"})


class UserTickerListSchema(Schema):
    """Schema para listagem de tickers do usuário"""

    tickers = fields.List(fields.Nested(UserTickerResponseSchema))
    total = fields.Int(metadata={"description": "Total de tickers"})
    page = fields.Int(metadata={"description": "Página atual"})
    per_page = fields.Int(metadata={"description": "Itens por página"})
