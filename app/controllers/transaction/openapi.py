from __future__ import annotations

from .utils import CONTRACT_HEADER

TAG_TRANSACTIONS = "Transações"
ERROR_TOKEN_INVALIDO = "Token inválido"
ERROR_INTERNO = "Erro interno"
ERROR_TRANSACAO_NAO_ENCONTRADA = "Transação não encontrada"
ERROR_SEM_PERMISSAO = "Sem permissão"
DESC_NUMERO_PAGINA = "Número da página"
DESC_ITENS_POR_PAGINA = "Itens por página"
DESC_DATA_INICIAL = "Data inicial (YYYY-MM-DD)"
DESC_DATA_FINAL = "Data final (YYYY-MM-DD)"

CONTRACT_HEADER_PARAM = {
    CONTRACT_HEADER: {
        "in": "header",
        "description": "Opcional. Envie 'v2' para o contrato padronizado.",
        "type": "string",
        "required": False,
    }
}

TRANSACTION_ID_PARAM = {
    "transaction_id": {"description": "ID da transação", "type": "string"}
}


TRANSACTION_CREATE_DOC = {
    "description": "Cria uma nova transação.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": CONTRACT_HEADER_PARAM,
    "responses": {
        201: {"description": "Transação criada com sucesso"},
        400: {"description": "Erro de validação"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_UPDATE_PATCH_DOC = {
    "description": "Atualiza parcialmente uma transação existente (contrato canônico).",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **CONTRACT_HEADER_PARAM},
    "responses": {
        200: {"description": "Transação atualizada"},
        400: {"description": "Erro de validação"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        403: {"description": ERROR_SEM_PERMISSAO},
        404: {"description": ERROR_TRANSACAO_NAO_ENCONTRADA},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_UPDATE_PUT_COMPAT_DOC = {
    **TRANSACTION_UPDATE_PATCH_DOC,
    "description": (
        "Compatibilidade transitória para update parcial. "
        "Prefira PATCH /transactions/{transaction_id}."
    ),
}
TRANSACTION_UPDATE_DOC = TRANSACTION_UPDATE_PATCH_DOC

TRANSACTION_SOFT_DELETE_DOC = {
    "description": "Realiza soft delete de uma transação.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **CONTRACT_HEADER_PARAM},
    "responses": {
        200: {"description": "Transação deletada"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        403: {"description": ERROR_SEM_PERMISSAO},
        404: {"description": ERROR_TRANSACAO_NAO_ENCONTRADA},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_RESTORE_DOC = {
    "description": "Restaura uma transação deletada logicamente.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **CONTRACT_HEADER_PARAM},
    "responses": {
        200: {"description": "Transação restaurada"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        404: {"description": ERROR_TRANSACAO_NAO_ENCONTRADA},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_DELETED_LIST_DOC = {
    "description": "Lista transações deletadas do usuário.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": CONTRACT_HEADER_PARAM,
    "responses": {
        200: {"description": "Lista de transações deletadas"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_ACTIVE_LIST_DOC = {
    "description": "Lista canônica de transações ativas com filtros e paginação.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "page": {"description": DESC_NUMERO_PAGINA, "type": "integer"},
        "per_page": {"description": DESC_ITENS_POR_PAGINA, "type": "integer"},
        "type": {"description": "Tipo (income|expense)", "type": "string"},
        "status": {"description": "Status da transação", "type": "string"},
        "start_date": {"description": DESC_DATA_INICIAL, "type": "string"},
        "end_date": {"description": DESC_DATA_FINAL, "type": "string"},
        "tag_id": {"description": "Filtrar por tag", "type": "string"},
        "account_id": {"description": "Filtrar por conta", "type": "string"},
        "credit_card_id": {
            "description": "Filtrar por cartão de crédito",
            "type": "string",
        },
        **CONTRACT_HEADER_PARAM,
    },
    "responses": {
        200: {"description": "Lista de transações"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_ACTIVE_LIST_LEGACY_DOC = {
    **TRANSACTION_ACTIVE_LIST_DOC,
    "description": (
        "Compatibilidade transitória para listagem de transações ativas. "
        "Prefira GET /transactions."
    ),
}

TRANSACTION_DETAIL_DOC = {
    "description": "Retorna o detalhe canônico de uma transação do usuário.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **CONTRACT_HEADER_PARAM},
    "responses": {
        200: {"description": "Detalhe da transação"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        403: {"description": ERROR_SEM_PERMISSAO},
        404: {"description": ERROR_TRANSACAO_NAO_ENCONTRADA},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_SUMMARY_DOC = {
    "description": "Resumo mensal de transações por mês (YYYY-MM).",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "month": {
            "description": "Mês de referência no formato YYYY-MM",
            "in": "query",
            "type": "string",
        },
        "page": {"description": DESC_NUMERO_PAGINA, "type": "integer"},
        "per_page": {
            "description": (
                f"{DESC_ITENS_POR_PAGINA}. Aceita 'page_size' temporariamente."
            ),
            "type": "integer",
        },
        **CONTRACT_HEADER_PARAM,
    },
    "responses": {
        200: {"description": "Resumo mensal"},
        400: {"description": "Parâmetro inválido"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_DASHBOARD_DOC = {
    "description": "Dashboard mensal com totais, contagens e categorias.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "month": {
            "description": "Mês de referência no formato YYYY-MM",
            "in": "query",
            "type": "string",
        },
        **CONTRACT_HEADER_PARAM,
    },
    "responses": {
        200: {"description": "Dashboard mensal"},
        400: {"description": "Parâmetro inválido"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_FORCE_DELETE_DOC = {
    "description": "Remove permanentemente uma transação já deletada.",
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **CONTRACT_HEADER_PARAM},
    "responses": {
        200: {"description": "Transação removida permanentemente"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        404: {"description": ERROR_TRANSACAO_NAO_ENCONTRADA},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_EXPENSE_PERIOD_DOC = {
    "description": (
        "Compatibilidade transitória para despesas por período. "
        "Prefira GET /transactions?type=expense com start_date/end_date."
    ),
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "start_date": {
            "description": f"{DESC_DATA_INICIAL}. Aceita 'startDate' temporariamente.",
            "type": "string",
        },
        "end_date": {
            "description": f"{DESC_DATA_FINAL}. Aceita 'finalDate' temporariamente.",
            "type": "string",
        },
        "page": {"description": DESC_NUMERO_PAGINA, "type": "integer"},
        "per_page": {"description": DESC_ITENS_POR_PAGINA, "type": "integer"},
        "order_by": {
            "description": "Campo de ordenação (due_date|created_at|amount|title)",
            "type": "string",
        },
        "order": {"description": "Direção (asc|desc)", "type": "string"},
        **CONTRACT_HEADER_PARAM,
    },
    "responses": {
        200: {"description": "Lista de despesas"},
        400: {"description": "Parâmetros inválidos"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        500: {"description": ERROR_INTERNO},
    },
}

TRANSACTION_DUE_PERIOD_DOC = {
    "description": (
        "Lista vencimentos (receitas + despesas) por período com paginação, "
        "contadores e ordenação por vencimento."
    ),
    "tags": [TAG_TRANSACTIONS],
    "security": [{"BearerAuth": []}],
    "params": {
        "start_date": {
            "description": (
                f"{DESC_DATA_INICIAL}. Aceita 'initialDate' temporariamente."
            ),
            "type": "string",
        },
        "end_date": {
            "description": f"{DESC_DATA_FINAL}. Aceita 'finalDate' temporariamente.",
            "type": "string",
        },
        "page": {"description": DESC_NUMERO_PAGINA, "type": "integer"},
        "per_page": {"description": DESC_ITENS_POR_PAGINA, "type": "integer"},
        "order_by": {
            "description": ("Ordenação (overdue_first|upcoming_first|date|title|card)"),
            "type": "string",
        },
        **CONTRACT_HEADER_PARAM,
    },
    "responses": {
        200: {"description": "Lista de vencimentos"},
        400: {"description": "Parâmetros inválidos"},
        401: {"description": ERROR_TOKEN_INVALIDO},
        500: {"description": ERROR_INTERNO},
    },
}
