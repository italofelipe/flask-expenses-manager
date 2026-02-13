from marshmallow import Schema, ValidationError, fields, pre_load, validates_schema

from app.schemas.sanitization import sanitize_string_fields


class AuthSchema(Schema):
    """Schema para autenticação de usuários"""

    email = fields.String(
        load_default=None,
        metadata={
            "description": "Endereço de email do usuário",
            "example": "joao.silva@email.com",
        },
    )
    name = fields.String(
        load_default=None,
        metadata={
            "description": "Nome do usuário (alternativa ao email)",
            "example": "João Silva",
        },
    )
    password = fields.String(
        required=True,
        metadata={
            "description": "Senha do usuário",
            "example": "minhasenha123",
        },
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(data, {"email", "name"})
        if isinstance(sanitized, dict) and isinstance(sanitized.get("email"), str):
            sanitized["email"] = str(sanitized["email"]).lower()
        return sanitized

    @validates_schema
    def validate_identity(self, data: dict[str, str], **kwargs: object) -> None:
        if not data.get("email") and not data.get("name"):
            raise ValidationError("Either 'email' or 'name' must be provided.")


class AuthSuccessResponseSchema(Schema):
    """Schema para resposta de autenticação bem-sucedida"""

    message = fields.String(
        required=True,
        metadata={
            "description": "Mensagem de sucesso",
            "example": "Login realizado com sucesso",
        },
    )
    token = fields.String(
        required=True,
        metadata={
            "description": "Token JWT para autenticação",
            "example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        },
    )
    user = fields.Dict(
        required=True,
        keys=fields.String(),
        values=fields.String(),
        metadata={"description": "Dados básicos do usuário autenticado"},
    )


class LogoutSchema(Schema):
    """Schema para logout de usuários"""

    message = fields.String(
        required=True,
        metadata={
            "description": "Mensagem de confirmação do logout",
            "example": "Logout realizado com sucesso",
        },
    )
