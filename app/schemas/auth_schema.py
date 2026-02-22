from marshmallow import (
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)

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


class ForgotPasswordSchema(Schema):
    """Schema para solicitação de recuperação de senha"""

    email = fields.Email(
        required=True,
        metadata={
            "description": "Email da conta que deseja recuperar acesso",
            "example": "joao.silva@email.com",
        },
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(data, {"email"})
        if isinstance(sanitized, dict) and isinstance(sanitized.get("email"), str):
            sanitized["email"] = str(sanitized["email"]).lower()
        return sanitized


class ResetPasswordSchema(Schema):
    """Schema para redefinição de senha via token"""

    token = fields.String(
        required=True,
        validate=validate.Length(min=24, max=512),
        metadata={
            "description": "Token de recuperação recebido por email",
            "example": "G9Q7zJ6lQ4Vwm6dXj6nQjzH8QqfUuBqbMTe4PmS7p8Q",
        },
    )
    new_password = fields.String(
        required=True,
        load_only=True,
        validate=validate.Regexp(
            r"^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}$",
            error=(
                "A senha deve ter no mínimo 10 caracteres, conter ao menos "
                "uma letra maiúscula, um número e um símbolo."
            ),
        ),
        metadata={
            "description": (
                "Nova senha (mínimo 10 caracteres, com maiúscula, número e símbolo)"
            ),
            "example": "NovaSenha@123",
        },
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        return sanitize_string_fields(data, {"token"})
