from __future__ import annotations

from typing import cast

from app.docs.openapi_helpers import (
    OpenAPIDict,
    contract_header_param,
    deprecated_headers_doc,
    json_error_response,
    json_request_body,
    json_success_response,
)
from app.schemas.transaction_schema import TransactionSchema

TAG_TRANSACTIONS = "Transações"
ERROR_TOKEN_INVALIDO = "Token revogado"
ERROR_INTERNO = "Erro interno"
ERROR_TRANSACAO_NAO_ENCONTRADA = "Transação não encontrada"
ERROR_SEM_PERMISSAO = "Sem permissão"
DESC_NUMERO_PAGINA = "Número da página"
DESC_ITENS_POR_PAGINA = "Itens por página"
DESC_DATA_INICIAL = "Data inicial (YYYY-MM-DD)"
DESC_DATA_FINAL = "Data final (YYYY-MM-DD)"
CONTRACT_HEADER_PARAM = contract_header_param()

TRANSACTION_ID_PARAM = {
    "transaction_id": {
        "description": "ID da transação",
        "type": "string",
        "example": "cfef66a6-a148-49db-a72f-cc63b6080cf8",
    }
}

TRANSACTION_EXAMPLE = {
    "id": "cfef66a6-a148-49db-a72f-cc63b6080cf8",
    "title": "Conta de luz",
    "description": "Fatura mensal de energia",
    "observation": "Pagar antes do dia 10",
    "is_recurring": False,
    "is_installment": False,
    "installment_count": None,
    "amount": "150.00",
    "currency": "BRL",
    "source": "manual",
    "external_id": None,
    "bank_name": None,
    "status": "pending",
    "type": "expense",
    "due_date": "2026-03-10",
    "start_date": None,
    "end_date": None,
    "tag_id": "73c3b094-60bf-45d5-8e32-0f673b2ab4a2",
    "account_id": "2d16ea71-b7ae-4da7-adc4-e93e54cd52cb",
    "credit_card_id": None,
    "installment_group_id": None,
    "paid_at": None,
    "created_at": "2026-03-01T10:00:00+00:00",
    "updated_at": "2026-03-01T10:00:00+00:00",
}

TRANSACTION_CREATE_PAYLOAD_EXAMPLE = {
    "title": "Conta de luz",
    "description": "Fatura mensal de energia",
    "observation": "Pagar antes do dia 10",
    "amount": "150.00",
    "type": "expense",
    "status": "pending",
    "due_date": "2026-03-10",
    "tag_id": "73c3b094-60bf-45d5-8e32-0f673b2ab4a2",
    "account_id": "2d16ea71-b7ae-4da7-adc4-e93e54cd52cb",
}

TRANSACTION_LIST_META_EXAMPLE = {
    "pagination": {"total": 14, "page": 1, "per_page": 10, "pages": 2},
}

TRANSACTION_CREATE_DOC = {
    "summary": "Criar transação",
    "description": (
        "Cria uma nova transação financeira.\n\n"
        "Aceita receitas e despesas, com suporte a recorrência e parcelamento."
    ),
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": contract_header_param(supported_version="v2"),
    "requestBody": json_request_body(
        schema=TransactionSchema,
        description="Payload de criação da transação.",
        example=TRANSACTION_CREATE_PAYLOAD_EXAMPLE,
    ),
    "responses": {
        201: json_success_response(
            description="Transação criada com sucesso",
            message="Transação criada com sucesso",
            data_example={"transaction": TRANSACTION_EXAMPLE},
        ),
        400: json_error_response(
            description="Erro de validação",
            message="Erro de validação",
            error_code="VALIDATION_ERROR",
            status_code=400,
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao criar transação",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_UPDATE_PATCH_DOC = {
    "summary": "Atualizar transação parcialmente",
    "description": (
        "Atualiza parcialmente uma transação existente. Este é o contrato "
        "canônico de update do MVP1."
    ),
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **contract_header_param(supported_version="v2")},
    "requestBody": json_request_body(
        schema=TransactionSchema(partial=True),
        description="Campos parciais a serem atualizados.",
        example={"status": "paid", "paid_at": "2026-03-10T12:00:00+00:00"},
    ),
    "responses": {
        200: json_success_response(
            description="Transação atualizada",
            message="Transação atualizada com sucesso",
            data_example={"transaction": {**TRANSACTION_EXAMPLE, "status": "paid"}},
        ),
        400: json_error_response(
            description="Erro de validação",
            message="Erro de validação",
            error_code="VALIDATION_ERROR",
            status_code=400,
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        403: json_error_response(
            description=ERROR_SEM_PERMISSAO,
            message=ERROR_SEM_PERMISSAO,
            error_code="FORBIDDEN",
            status_code=403,
        ),
        404: json_error_response(
            description=ERROR_TRANSACAO_NAO_ENCONTRADA,
            message=ERROR_TRANSACAO_NAO_ENCONTRADA,
            error_code="NOT_FOUND",
            status_code=404,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao atualizar transação",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_UPDATE_PUT_COMPAT_DOC = {
    **TRANSACTION_UPDATE_PATCH_DOC,
    "summary": "Atualizar transação (compatibilidade PUT)",
    "description": (
        "Compatibilidade transitória para update parcial. "
        "Prefira `PATCH /transactions/{transaction_id}`."
    ),
}
transaction_update_put_responses = cast(
    dict[object, object],
    dict(cast(OpenAPIDict, TRANSACTION_UPDATE_PATCH_DOC["responses"])),
)
transaction_update_put_responses[200] = json_success_response(
    description="Transação atualizada (compatibilidade transitória)",
    message="Transação atualizada com sucesso",
    data_example={"transaction": {**TRANSACTION_EXAMPLE, "status": "paid"}},
    headers=deprecated_headers_doc(
        successor_endpoint="/transactions/{transaction_id}",
        successor_method="PATCH",
    ),
)
TRANSACTION_UPDATE_PUT_COMPAT_DOC["responses"] = transaction_update_put_responses
TRANSACTION_UPDATE_DOC = TRANSACTION_UPDATE_PATCH_DOC
TRANSACTION_UPDATE_DOC = TRANSACTION_UPDATE_PATCH_DOC

TRANSACTION_SOFT_DELETE_DOC = {
    "summary": "Remover transação logicamente",
    "description": "Realiza soft delete de uma transação do usuário autenticado.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **contract_header_param(supported_version="v2")},
    "responses": {
        200: json_success_response(
            description="Transação deletada",
            message="Transação deletada com sucesso",
            data_example={"transaction_id": TRANSACTION_EXAMPLE["id"]},
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        403: json_error_response(
            description=ERROR_SEM_PERMISSAO,
            message=ERROR_SEM_PERMISSAO,
            error_code="FORBIDDEN",
            status_code=403,
        ),
        404: json_error_response(
            description=ERROR_TRANSACAO_NAO_ENCONTRADA,
            message=ERROR_TRANSACAO_NAO_ENCONTRADA,
            error_code="NOT_FOUND",
            status_code=404,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao deletar transação",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_RESTORE_DOC = {
    "summary": "Restaurar transação deletada",
    "description": "Restaura uma transação deletada logicamente.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **contract_header_param(supported_version="v2")},
    "responses": {
        200: json_success_response(
            description="Transação restaurada",
            message="Transação restaurada com sucesso",
            data_example={"transaction": TRANSACTION_EXAMPLE},
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        404: json_error_response(
            description=ERROR_TRANSACAO_NAO_ENCONTRADA,
            message=ERROR_TRANSACAO_NAO_ENCONTRADA,
            error_code="NOT_FOUND",
            status_code=404,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao restaurar transação",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_DELETED_LIST_DOC = {
    "summary": "Listar transações deletadas",
    "description": "Lista a lixeira de transações deletadas do usuário.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": contract_header_param(supported_version="v2"),
    "responses": {
        200: json_success_response(
            description="Lista de transações deletadas",
            message="Lista de transações deletadas",
            data_example={"items": [TRANSACTION_EXAMPLE]},
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao listar transações deletadas",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_ACTIVE_LIST_DOC = {
    "summary": "Listar transações",
    "description": (
        "Lista canônica de transações ativas com filtros, ordenação e paginação."
    ),
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "page": {"description": DESC_NUMERO_PAGINA, "type": "integer", "example": 1},
        "per_page": {
            "description": DESC_ITENS_POR_PAGINA,
            "type": "integer",
            "example": 10,
        },
        "type": {
            "description": "Tipo (income|expense)",
            "type": "string",
            "example": "expense",
        },
        "status": {
            "description": "Status da transação",
            "type": "string",
            "example": "pending",
        },
        "start_date": {
            "description": DESC_DATA_INICIAL,
            "type": "string",
            "example": "2026-03-01",
        },
        "end_date": {
            "description": DESC_DATA_FINAL,
            "type": "string",
            "example": "2026-03-31",
        },
        "tag_id": {"description": "Filtrar por tag", "type": "string"},
        "account_id": {"description": "Filtrar por conta", "type": "string"},
        "credit_card_id": {
            "description": "Filtrar por cartão de crédito",
            "type": "string",
        },
        **contract_header_param(supported_version="v2"),
    },
    "responses": {
        200: json_success_response(
            description="Lista de transações",
            message="Lista de transações retornada com sucesso",
            data_example={"items": [TRANSACTION_EXAMPLE]},
            meta_example=TRANSACTION_LIST_META_EXAMPLE,
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao listar transações",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_ACTIVE_LIST_LEGACY_DOC = {
    **TRANSACTION_ACTIVE_LIST_DOC,
    "summary": "Listar transações (compatibilidade /transactions/list)",
    "description": (
        "Compatibilidade transitória para listagem de transações ativas. "
        "Prefira `GET /transactions`."
    ),
}
transaction_active_list_legacy_responses = cast(
    dict[object, object],
    dict(cast(OpenAPIDict, TRANSACTION_ACTIVE_LIST_DOC["responses"])),
)
transaction_active_list_legacy_responses[200] = json_success_response(
    description="Lista de transações (compatibilidade transitória)",
    message="Lista de transações retornada com sucesso",
    data_example={"items": [TRANSACTION_EXAMPLE]},
    meta_example=TRANSACTION_LIST_META_EXAMPLE,
    headers=deprecated_headers_doc(
        successor_endpoint="/transactions",
        successor_method="GET",
    ),
)
TRANSACTION_ACTIVE_LIST_LEGACY_DOC["responses"] = (
    transaction_active_list_legacy_responses
)

TRANSACTION_DETAIL_DOC = {
    "summary": "Obter detalhe de transação",
    "description": "Retorna o detalhe canônico de uma transação do usuário.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **contract_header_param(supported_version="v2")},
    "responses": {
        200: json_success_response(
            description="Detalhe da transação",
            message="Detalhe da transação retornado com sucesso",
            data_example={"transaction": TRANSACTION_EXAMPLE},
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        403: json_error_response(
            description=ERROR_SEM_PERMISSAO,
            message=ERROR_SEM_PERMISSAO,
            error_code="FORBIDDEN",
            status_code=403,
        ),
        404: json_error_response(
            description=ERROR_TRANSACAO_NAO_ENCONTRADA,
            message=ERROR_TRANSACAO_NAO_ENCONTRADA,
            error_code="NOT_FOUND",
            status_code=404,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao carregar transação",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_SUMMARY_DOC = {
    "summary": "Obter resumo mensal de transações",
    "description": "Resumo mensal de receitas, despesas e itens paginados por mês.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "month": {
            "description": "Mês de referência no formato YYYY-MM",
            "in": "query",
            "type": "string",
            "example": "2026-03",
        },
        "page": {"description": DESC_NUMERO_PAGINA, "type": "integer", "example": 1},
        "per_page": {
            "description": (
                f"{DESC_ITENS_POR_PAGINA}. Aceita `page_size` temporariamente."
            ),
            "type": "integer",
            "example": 10,
        },
        **contract_header_param(supported_version="v2"),
    },
    "responses": {
        200: json_success_response(
            description="Resumo mensal",
            message="Resumo mensal retornado com sucesso",
            data_example={
                "month": "2026-03",
                "income_total": 5000.0,
                "expense_total": 3200.0,
                "transactions": [TRANSACTION_EXAMPLE],
            },
            meta_example={"pagination": {"total": 14, "page": 1, "per_page": 10}},
        ),
        400: json_error_response(
            description="Parâmetro inválido",
            message="Parâmetro 'month' inválido. Use o formato YYYY-MM.",
            error_code="VALIDATION_ERROR",
            status_code=400,
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao calcular resumo mensal",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_DASHBOARD_DOC = {
    "summary": "Obter dashboard mensal legado de transações",
    "description": (
        "Compatibilidade transitória para o dashboard mensal. "
        "Prefira `GET /dashboard/overview`."
    ),
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "month": {
            "description": "Mês de referência no formato YYYY-MM",
            "in": "query",
            "type": "string",
            "example": "2026-03",
        },
        **contract_header_param(supported_version="v2"),
    },
    "responses": {
        200: json_success_response(
            description="Dashboard mensal legado",
            message="Dashboard mensal retornado com sucesso",
            data_example={
                "month": "2026-03",
                "income_total": 5000.0,
                "expense_total": 3200.0,
                "balance": 1800.0,
                "counts": {
                    "total_transactions": 14,
                    "income_transactions": 4,
                    "expense_transactions": 10,
                },
            },
            headers=deprecated_headers_doc(
                successor_endpoint="/dashboard/overview",
                successor_method="GET",
            ),
        ),
        400: json_error_response(
            description="Parâmetro inválido",
            message="Parâmetro 'month' inválido. Use o formato YYYY-MM.",
            error_code="VALIDATION_ERROR",
            status_code=400,
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao calcular dashboard mensal",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_FORCE_DELETE_DOC = {
    "summary": "Remover transação permanentemente",
    "description": "Remove permanentemente uma transação já deletada logicamente.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **contract_header_param(supported_version="v2")},
    "responses": {
        200: json_success_response(
            description="Transação removida permanentemente",
            message="Transação removida permanentemente",
            data_example={"transaction_id": TRANSACTION_EXAMPLE["id"]},
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        404: json_error_response(
            description=ERROR_TRANSACAO_NAO_ENCONTRADA,
            message=ERROR_TRANSACAO_NAO_ENCONTRADA,
            error_code="NOT_FOUND",
            status_code=404,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao remover transação",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_EXPENSE_PERIOD_DOC = {
    "summary": "Listar despesas por período (compatibilidade)",
    "description": (
        "Compatibilidade transitória para despesas por período. "
        "Prefira `GET /transactions?type=expense&start_date=...&end_date=...`."
    ),
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "start_date": {
            "description": f"{DESC_DATA_INICIAL}. Aceita `startDate` temporariamente.",
            "type": "string",
            "example": "2026-03-01",
        },
        "end_date": {
            "description": f"{DESC_DATA_FINAL}. Aceita `finalDate` temporariamente.",
            "type": "string",
            "example": "2026-03-31",
        },
        "page": {"description": DESC_NUMERO_PAGINA, "type": "integer", "example": 1},
        "per_page": {
            "description": DESC_ITENS_POR_PAGINA,
            "type": "integer",
            "example": 10,
        },
        "order_by": {
            "description": "Campo de ordenação (due_date|created_at|amount|title)",
            "type": "string",
            "example": "due_date",
        },
        "order": {
            "description": "Direção (asc|desc)",
            "type": "string",
            "example": "asc",
        },
        **contract_header_param(supported_version="v2"),
    },
    "responses": {
        200: json_success_response(
            description="Lista de despesas",
            message="Lista de despesas por período",
            data_example={
                "expenses": [TRANSACTION_EXAMPLE],
                "counts": {
                    "total_transactions": 14,
                    "income_transactions": 4,
                    "expense_transactions": 10,
                },
            },
            meta_example=TRANSACTION_LIST_META_EXAMPLE,
            headers=deprecated_headers_doc(
                successor_endpoint="/transactions",
                successor_method="GET",
            ),
        ),
        400: json_error_response(
            description="Parâmetros inválidos",
            message="Parâmetros de período inválidos.",
            error_code="VALIDATION_ERROR",
            status_code=400,
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao listar despesas por período",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

TRANSACTION_DUE_PERIOD_DOC = {
    "summary": "Listar vencimentos por período",
    "description": (
        "Lista vencimentos (receitas + despesas) por período com paginação, "
        "contadores e ordenação por vencimento."
    ),
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "start_date": {
            "description": (
                f"{DESC_DATA_INICIAL}. Aceita `initialDate` temporariamente."
            ),
            "type": "string",
            "example": "2026-03-01",
        },
        "end_date": {
            "description": f"{DESC_DATA_FINAL}. Aceita `finalDate` temporariamente.",
            "type": "string",
            "example": "2026-03-31",
        },
        "page": {"description": DESC_NUMERO_PAGINA, "type": "integer", "example": 1},
        "per_page": {
            "description": DESC_ITENS_POR_PAGINA,
            "type": "integer",
            "example": 10,
        },
        "order_by": {
            "description": "Ordenação (overdue_first|upcoming_first|date|title|card)",
            "type": "string",
            "example": "overdue_first",
        },
        **contract_header_param(supported_version="v2"),
    },
    "responses": {
        200: json_success_response(
            description="Lista de vencimentos",
            message="Lista de vencimentos retornada com sucesso",
            data_example={
                "items": [TRANSACTION_EXAMPLE],
                "counts": {
                    "total_transactions": 14,
                    "income_transactions": 4,
                    "expense_transactions": 10,
                },
            },
            meta_example=TRANSACTION_LIST_META_EXAMPLE,
        ),
        400: json_error_response(
            description="Parâmetros inválidos",
            message="Parâmetros de período inválidos.",
            error_code="VALIDATION_ERROR",
            status_code=400,
        ),
        401: json_error_response(
            description=ERROR_TOKEN_INVALIDO,
            message=ERROR_TOKEN_INVALIDO,
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        500: json_error_response(
            description=ERROR_INTERNO,
            message="Erro ao listar vencimentos",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}
