from marshmallow import Schema, fields, pre_load, validate

from app.schemas.sanitization import sanitize_string_fields


class TransactionSchema(Schema):
    """Schema para criação e atualização de transações financeiras"""

    class Meta:
        name = "TransactionCreate"
        ordered = True

    id = fields.UUID(
        dump_only=True, description="ID único da transação (gerado automaticamente)"
    )
    user_id = fields.UUID(
        dump_only=True, description="ID do usuário proprietário da transação"
    )
    title = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=120),
        description="Título da transação",
        example="Pagamento da conta de luz",
    )
    description = fields.Str(
        validate=validate.Length(max=300),
        description="Descrição detalhada da transação",
        example="Conta de energia elétrica do mês de janeiro",
    )
    observation = fields.Str(
        validate=validate.Length(max=500),
        description="Observações adicionais sobre a transação",
        example="Pagar até o dia 10 para evitar multa",
    )
    is_recurring = fields.Bool(
        description="Indica se a transação é recorrente", example=False
    )
    is_installment = fields.Bool(
        description="Indica se a transação é parcelada", example=False
    )
    installment_count = fields.Int(
        validate=validate.Range(min=1, max=60),
        description="Número de parcelas (apenas se is_installment=True)",
        example=12,
    )
    amount = fields.Decimal(
        as_string=True,
        required=True,
        validate=validate.Range(min=0.01),
        description="Valor da transação",
        example="150.50",
    )
    currency = fields.Str(
        validate=validate.Length(equal=3),
        description="Código da moeda (ISO 4217)",
        example="BRL",
    )
    status = fields.Str(
        validate=validate.OneOf(
            ["paid", "pending", "cancelled", "postponed", "overdue"]
        ),
        description="Status atual da transação",
        example="pending",
    )
    type = fields.Str(
        required=True,
        validate=validate.OneOf(["income", "expense"]),
        description="Tipo da transação: receita ou despesa",
        example="expense",
    )
    due_date = fields.Date(
        required=True,
        description="Data de vencimento da transação",
        example="2024-02-15",
    )
    start_date = fields.Date(
        description="Data de início (para transações recorrentes)", example="2024-01-01"
    )
    end_date = fields.Date(
        description="Data de fim (para transações recorrentes)", example="2024-12-31"
    )
    tag_id = fields.UUID(allow_none=True, description="ID da tag associada à transação")
    account_id = fields.UUID(
        allow_none=True, description="ID da conta bancária associada"
    )
    credit_card_id = fields.UUID(
        allow_none=True, description="ID do cartão de crédito associado"
    )
    installment_group_id = fields.UUID(
        dump_only=True, description="ID do grupo de parcelas (gerado automaticamente)"
    )
    paid_at = fields.DateTime(
        allow_none=True,
        description="Data e hora do pagamento",
        example="2024-02-10T14:30:00Z",
    )
    created_at = fields.DateTime(
        dump_only=True, description="Data de criação da transação"
    )
    updated_at = fields.DateTime(
        dump_only=True, description="Data da última atualização"
    )

    @pre_load  # type: ignore[misc]
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(
            data,
            {
                "title",
                "description",
                "observation",
                "type",
                "status",
                "currency",
            },
        )
        if isinstance(sanitized, dict):
            if isinstance(sanitized.get("type"), str):
                sanitized["type"] = str(sanitized["type"]).lower()
            if isinstance(sanitized.get("status"), str):
                sanitized["status"] = str(sanitized["status"]).lower()
            if isinstance(sanitized.get("currency"), str):
                sanitized["currency"] = str(sanitized["currency"]).upper()
        return sanitized


class TransactionResponseSchema(Schema):
    """Schema para resposta de transações"""

    class Meta:
        name = "TransactionResponse"
        ordered = True

    id = fields.UUID(description="ID único da transação")
    user_id = fields.UUID(description="ID do usuário")
    title = fields.Str(description="Título da transação")
    description = fields.Str(description="Descrição da transação")
    observation = fields.Str(description="Observações")
    is_recurring = fields.Bool(description="Se é recorrente")
    is_installment = fields.Bool(description="Se é parcelada")
    installment_count = fields.Int(description="Número de parcelas")
    amount = fields.Decimal(as_string=True, description="Valor da transação")
    currency = fields.Str(description="Moeda")
    status = fields.Str(description="Status da transação")
    type = fields.Str(description="Tipo da transação")
    due_date = fields.Date(description="Data de vencimento")
    start_date = fields.Date(description="Data de início")
    end_date = fields.Date(description="Data de fim")
    tag_id = fields.UUID(description="ID da tag")
    account_id = fields.UUID(description="ID da conta")
    credit_card_id = fields.UUID(description="ID do cartão de crédito")
    installment_group_id = fields.UUID(description="ID do grupo de parcelas")
    paid_at = fields.DateTime(description="Data do pagamento")
    created_at = fields.DateTime(description="Data de criação")
    updated_at = fields.DateTime(description="Data de atualização")


class TransactionListSchema(Schema):
    """Schema para listagem de transações"""

    class Meta:
        name = "TransactionList"
        ordered = True

    transactions = fields.List(fields.Nested(TransactionResponseSchema))
    total = fields.Int(description="Total de transações")
    page = fields.Int(description="Página atual")
    per_page = fields.Int(description="Itens por página")


class MonthlySummarySchema(Schema):
    """Schema para resumo mensal de transações"""

    class Meta:
        name = "MonthlySummary"
        ordered = True

    income_total = fields.Str(description="Total de receitas do mês")
    expense_total = fields.Str(description="Total de despesas do mês")
    transactions = fields.List(fields.Nested(TransactionResponseSchema))
