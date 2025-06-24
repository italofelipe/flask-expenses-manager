from marshmallow import Schema, fields


class ErrorResponseSchema(Schema):
    """Schema para respostas de erro da API"""

    error = fields.String(
        required=True, description="Tipo do erro", example="ValidationError"
    )
    message = fields.String(
        required=True,
        description="Mensagem descritiva do erro",
        example="Dados inválidos fornecidos",
    )
    details = fields.Dict(
        required=False,
        description="Detalhes adicionais do erro",
        example={"field": "email", "issue": "Email inválido"},
    )
    status_code = fields.Int(
        required=True, description="Código de status HTTP", example=400
    )
