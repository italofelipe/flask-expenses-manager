from marshmallow import Schema, fields, validate


class TagSchema(Schema):
    """Schema para criação e atualização de tags"""

    id = fields.UUID(
        dump_only=True, description="ID único da tag (gerado automaticamente)"
    )
    user_id = fields.UUID(
        required=False, description="ID do usuário proprietário da tag"
    )
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=50),
        description="Nome da tag para categorização",
        example="Alimentação",
    )


class TagResponseSchema(Schema):
    """Schema para resposta de tags"""

    id = fields.UUID(description="ID único da tag")
    user_id = fields.UUID(description="ID do usuário")
    name = fields.Str(description="Nome da tag")


class TagListSchema(Schema):
    """Schema para listagem de tags"""

    tags = fields.List(fields.Nested(TagResponseSchema))
    total = fields.Int(description="Total de tags")
    page = fields.Int(description="Página atual")
    per_page = fields.Int(description="Itens por página")
