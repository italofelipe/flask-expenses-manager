from __future__ import annotations

from app.controllers.transaction_controller_utils import CONTRACT_HEADER

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
    "tags": ["Transações"],
    "security": [{"BearerAuth": []}],
    "params": CONTRACT_HEADER_PARAM,
    "responses": {
        201: {"description": "Transação criada com sucesso"},
        400: {"description": "Erro de validação"},
        401: {"description": "Token inválido"},
        500: {"description": "Erro interno"},
    },
}

TRANSACTION_UPDATE_DOC = {
    "description": "Atualiza uma transação existente.",
    "tags": ["Transações"],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **CONTRACT_HEADER_PARAM},
    "responses": {
        200: {"description": "Transação atualizada"},
        400: {"description": "Erro de validação"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Transação não encontrada"},
        500: {"description": "Erro interno"},
    },
}

TRANSACTION_SOFT_DELETE_DOC = {
    "description": "Realiza soft delete de uma transação.",
    "tags": ["Transações"],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **CONTRACT_HEADER_PARAM},
    "responses": {
        200: {"description": "Transação deletada"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Transação não encontrada"},
        500: {"description": "Erro interno"},
    },
}

TRANSACTION_RESTORE_DOC = {
    "description": "Restaura uma transação deletada logicamente.",
    "tags": ["Transações"],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **CONTRACT_HEADER_PARAM},
    "responses": {
        200: {"description": "Transação restaurada"},
        401: {"description": "Token inválido"},
        404: {"description": "Transação não encontrada"},
        500: {"description": "Erro interno"},
    },
}

TRANSACTION_DELETED_LIST_DOC = {
    "description": "Lista transações deletadas do usuário.",
    "tags": ["Transações"],
    "security": [{"BearerAuth": []}],
    "params": CONTRACT_HEADER_PARAM,
    "responses": {
        200: {"description": "Lista de transações deletadas"},
        401: {"description": "Token inválido"},
        500: {"description": "Erro interno"},
    },
}

TRANSACTION_ACTIVE_LIST_DOC = {
    "description": "Lista transações ativas com filtros e paginação.",
    "tags": ["Transações"],
    "security": [{"BearerAuth": []}],
    "params": {
        "page": {"description": "Número da página", "type": "integer"},
        "per_page": {"description": "Itens por página", "type": "integer"},
        "type": {"description": "Tipo (income|expense)", "type": "string"},
        "status": {"description": "Status da transação", "type": "string"},
        "start_date": {"description": "Data inicial (YYYY-MM-DD)", "type": "string"},
        "end_date": {"description": "Data final (YYYY-MM-DD)", "type": "string"},
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
        401: {"description": "Token inválido"},
        500: {"description": "Erro interno"},
    },
}

TRANSACTION_SUMMARY_DOC = {
    "description": "Resumo mensal de transações por mês (YYYY-MM).",
    "tags": ["Transações"],
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
        200: {"description": "Resumo mensal"},
        400: {"description": "Parâmetro inválido"},
        401: {"description": "Token inválido"},
        500: {"description": "Erro interno"},
    },
}

TRANSACTION_DASHBOARD_DOC = {
    "description": "Dashboard mensal com totais, contagens e categorias.",
    "tags": ["Transações"],
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
        401: {"description": "Token inválido"},
        500: {"description": "Erro interno"},
    },
}

TRANSACTION_FORCE_DELETE_DOC = {
    "description": "Remove permanentemente uma transação já deletada.",
    "tags": ["Transações"],
    "security": [{"BearerAuth": []}],
    "params": {**TRANSACTION_ID_PARAM, **CONTRACT_HEADER_PARAM},
    "responses": {
        200: {"description": "Transação removida permanentemente"},
        401: {"description": "Token inválido"},
        404: {"description": "Transação não encontrada"},
        500: {"description": "Erro interno"},
    },
}

TRANSACTION_EXPENSE_PERIOD_DOC = {
    "description": "Lista despesas por período com paginação e contadores.",
    "tags": ["Transações"],
    "security": [{"BearerAuth": []}],
    "params": {
        "startDate": {"description": "Data inicial (YYYY-MM-DD)", "type": "string"},
        "finalDate": {"description": "Data final (YYYY-MM-DD)", "type": "string"},
        "page": {"description": "Número da página", "type": "integer"},
        "per_page": {"description": "Itens por página", "type": "integer"},
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
        401: {"description": "Token inválido"},
        500: {"description": "Erro interno"},
    },
}
