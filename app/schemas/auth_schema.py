from marshmallow import (
    Schema,
    fields,
    pre_load,
    validate,
)

from app.schemas.sanitization import sanitize_string_fields

EXAMPLE_USER_EMAIL = "joao.silva@email.com"


class AuthSchema(Schema):
    """Schema para autenticação de usuários"""

    email = fields.Email(
        required=True,
        metadata={
            "description": "Endereço de email do usuário (identificador canônico)",
            "example": EXAMPLE_USER_EMAIL,
        },
    )
    password = fields.String(
        required=True,
        metadata={
            "description": "Senha do usuário",
            "example": "minhasenha123",
        },
    )
    captcha_token = fields.String(
        required=False,
        allow_none=True,
        load_default=None,
        metadata={
            "description": (
                "Token Cloudflare Turnstile obtido pelo cliente. "
                "Obrigatório quando CAPTCHA está habilitado no servidor."
            ),
            "example": "0.xxxxxxxxxxx",
        },
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(data, {"email"})
        if not isinstance(sanitized, dict):
            return sanitized
        if isinstance(sanitized.get("email"), str):
            sanitized["email"] = str(sanitized["email"]).lower()
        # Normalize camelCase sent by TypeScript frontend clients → snake_case.
        if "captchaToken" in sanitized and "captcha_token" not in sanitized:
            sanitized["captcha_token"] = sanitized.pop("captchaToken")
        return sanitized


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
            "example": EXAMPLE_USER_EMAIL,
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


class ConfirmEmailSchema(Schema):
    """Schema para confirmacao de conta via token"""

    token = fields.String(
        required=True,
        validate=validate.Length(min=24, max=512),
        metadata={
            "description": "Token de confirmacao recebido por email",
            "example": "G9Q7zJ6lQ4Vwm6dXj6nQjzH8QqfUuBqbMTe4PmS7p8Q",
        },
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        return sanitize_string_fields(data, {"token"})


class ResendConfirmationSchema(Schema):
    """Schema para reenvio de confirmacao de conta"""

    email = fields.Email(
        required=True,
        metadata={
            "description": "Email da conta que deseja confirmar",
            "example": EXAMPLE_USER_EMAIL,
        },
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(data, {"email"})
        if isinstance(sanitized, dict) and isinstance(sanitized.get("email"), str):
            sanitized["email"] = str(sanitized["email"]).lower()
        return sanitized
