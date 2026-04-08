from __future__ import annotations

from typing import cast

from app.controllers.transaction.openapi_shared import (
    DESC_DATA_FINAL,
    DESC_DATA_INICIAL,
    DESC_ITENS_POR_PAGINA,
    DESC_NUMERO_PAGINA,
    ERROR_INTERNO,
    ERROR_SEM_PERMISSAO,
    ERROR_TOKEN_INVALIDO,
    ERROR_TRANSACAO_NAO_ENCONTRADA,
    TAG_TRANSACTIONS,
    TRANSACTION_EXAMPLE,
    TRANSACTION_ID_PARAM,
    TRANSACTION_LIST_META_EXAMPLE,
    OpenAPIDict,
    contract_header_param,
    deprecated_headers_doc,
    json_error_response,
    json_success_response,
)

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

__all__ = [
    "TRANSACTION_DELETED_LIST_DOC",
    "TRANSACTION_ACTIVE_LIST_DOC",
    "TRANSACTION_ACTIVE_LIST_LEGACY_DOC",
    "TRANSACTION_DETAIL_DOC",
    "TRANSACTION_SUMMARY_DOC",
    "TRANSACTION_DASHBOARD_DOC",
    "TRANSACTION_EXPENSE_PERIOD_DOC",
    "TRANSACTION_DUE_PERIOD_DOC",
]
