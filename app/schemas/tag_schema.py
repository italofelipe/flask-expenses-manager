from marshmallow import Schema, fields, validate


class TagSchema(Schema):
    """Schema para criação e atualização de tags"""

    id = fields.UUID(
        dump_only=True,
        metadata={"description": "ID único da tag (gerado automaticamente)"},
    )
    user_id = fields.UUID(
        required=False,
        metadata={"description": "ID do usuário proprietário da tag"},
    )
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=50),
        metadata={
            "description": "Nome da tag para categorização",
            "example": "Alimentação",
        },
    )


class TagResponseSchema(Schema):
    """Schema para resposta de tags"""

    id = fields.UUID(metadata={"description": "ID único da tag"})
    user_id = fields.UUID(metadata={"description": "ID do usuário"})
    name = fields.Str(metadata={"description": "Nome da tag"})


class TagListSchema(Schema):
    """Schema para listagem de tags"""

    tags = fields.List(fields.Nested(TagResponseSchema))
    total = fields.Int(metadata={"description": "Total de tags"})
    page = fields.Int(metadata={"description": "Página atual"})
    per_page = fields.Int(metadata={"description": "Itens por página"})
