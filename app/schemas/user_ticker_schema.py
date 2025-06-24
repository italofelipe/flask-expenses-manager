from marshmallow import Schema, fields, validate


class UserTickerSchema(Schema):
    """Schema para criação e atualização de tickers do usuário"""

    id = fields.UUID(
        dump_only=True, description="ID único do ticker (gerado automaticamente)"
    )
    symbol = fields.String(
        required=True,
        validate=validate.Length(min=1, max=10),
        description="Símbolo do ativo (ex: PETR4, VALE3)",
        example="PETR4",
    )
    quantity = fields.Float(
        required=True,
        validate=validate.Range(min=0.01),
        description="Quantidade de ações/ativos possuídos",
        example=100.0,
    )
    type = fields.String(
        required=False,
        validate=validate.OneOf(["stock", "fii", "etf", "bond", "crypto", "other"]),
        description="Tipo do ativo",
        example="stock",
    )
    user_id = fields.UUID(
        dump_only=True, description="ID do usuário proprietário do ticker"
    )


class UserTickerResponseSchema(Schema):
    """Schema para resposta de tickers do usuário"""

    id = fields.UUID(description="ID único do ticker")
    symbol = fields.String(description="Símbolo do ativo")
    quantity = fields.Float(description="Quantidade possuída")
    type = fields.String(description="Tipo do ativo")
    user_id = fields.UUID(description="ID do usuário")


class UserTickerListSchema(Schema):
    """Schema para listagem de tickers do usuário"""

    tickers = fields.List(fields.Nested(UserTickerResponseSchema))
    total = fields.Int(description="Total de tickers")
    page = fields.Int(description="Página atual")
    per_page = fields.Int(description="Itens por página")
