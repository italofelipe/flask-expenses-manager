import re

from marshmallow import Schema, ValidationError, fields, validate

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_hex_color(value: str) -> None:
    if value is not None and not _HEX_COLOR_RE.match(value):
        raise ValidationError("Color must be a valid hex color code (e.g. #FF6B6B)")


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
    color = fields.Str(
        required=False,
        allow_none=True,
        validate=_validate_hex_color,
        metadata={
            "description": "Cor da tag no formato hexadecimal",
            "example": "#FF6B6B",
        },
    )
    icon = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=50),
        metadata={
            "description": "Ícone da tag (emoji ou chave de ícone)",
            "example": "🍔",
        },
    )


class TagResponseSchema(Schema):
    """Schema para resposta de tags"""

    id = fields.UUID(metadata={"description": "ID único da tag"})
    user_id = fields.UUID(metadata={"description": "ID do usuário"})
    name = fields.Str(metadata={"description": "Nome da tag"})
    color = fields.Str(allow_none=True, metadata={"description": "Cor da tag"})
    icon = fields.Str(allow_none=True, metadata={"description": "Ícone da tag"})


class TagListSchema(Schema):
    """Schema para listagem de tags"""

    tags = fields.List(fields.Nested(TagResponseSchema))
    total = fields.Int(metadata={"description": "Total de tags"})
    page = fields.Int(metadata={"description": "Página atual"})
    per_page = fields.Int(metadata={"description": "Itens por página"})
