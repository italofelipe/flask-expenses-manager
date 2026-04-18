"""OpenAPI doc kwargs for the wallet domain endpoints."""

from __future__ import annotations

from typing import Any

from app.docs.openapi_helpers import deprecated_headers_doc

WALLET_UPDATE_SUCCESSOR_ENDPOINT = "/wallet/{investment_id}"
WALLET_UPDATE_SUCCESSOR_METHOD = "PATCH"
WALLET_UPDATE_SUCCESS_MESSAGE = "Investimento atualizado com sucesso"

WALLET_ADD_DOC: dict[str, Any] = {
    "description": (
        "Adiciona um novo item à carteira do usuário.\n\n"
        "Você pode informar um valor fixo (como R$1000,00 em poupança) "
        "ou um ativo com ticker.\n\n"
        "Regras:\n"
        "- Se informar o campo 'ticker', o campo 'value' será ignorado.\n"
        "- Se não informar 'ticker', é obrigatório informar 'value'.\n"
        "- Se informar 'ticker', também é obrigatório informar 'quantity'.\n\n"
        "Exemplo com valor fixo:\n"
        "{'name': 'Poupança', 'value': 1500.00, 'register_date': "
        "'2024-07-01', 'should_be_on_wallet': true}\n\n"
        "Exemplo com ticker:\n"
        "{'name': 'Investimento PETR4', 'ticker': 'petr4', 'quantity': 10, "
        "'register_date': '2024-07-01', 'should_be_on_wallet': true}\n\n"
        "Resposta esperada:\n"
        "{'message': 'Ativo cadastrado com sucesso'}"
    ),
    "tags": ["Wallet"],
    "security": [{"BearerAuth": []}],
    "responses": {
        201: {"description": "Ativo cadastrado com sucesso"},
        400: {"description": "Erro de validação ou ticker inválido"},
        401: {"description": "Token inválido"},
        500: {"description": "Erro interno"},
    },
}

WALLET_LIST_DOC: dict[str, Any] = {
    "description": "Lista os investimentos cadastrados na carteira com paginação.",
    "tags": ["Wallet"],
    "security": [{"BearerAuth": []}],
    "params": {
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        }
    },
    "responses": {
        200: {"description": "Lista paginada de investimentos"},
        401: {"description": "Token inválido"},
    },
}

WALLET_GET_DOC: dict[str, Any] = {
    "description": (
        "Retorna o detalhe canônico de um investimento específico da carteira "
        "do usuário autenticado."
    ),
    "tags": ["Wallet"],
    "security": [{"BearerAuth": []}],
    "params": {
        "investment_id": {"description": "ID do investimento"},
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    "responses": {
        200: {"description": "Investimento retornado com sucesso"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Investimento não encontrado"},
    },
}

WALLET_HISTORY_DOC: dict[str, Any] = {
    "description": (
        "Retorna o histórico de alterações de um investimento, "
        + "paginado e ordenado."
    ),
    "tags": ["Wallet"],
    "security": [{"BearerAuth": []}],
    "params": {
        "investment_id": {"description": "ID do investimento"},
        "page": {"description": "Página desejada (default: 1)"},
        "per_page": {
            "description": "Itens por página (default: 5, mínimo 1, máximo 100)"
        },
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    "responses": {
        200: {"description": "Histórico paginado"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão"},
        404: {"description": "Investimento não encontrado"},
    },
}

WALLET_PATCH_DOC: dict[str, Any] = {
    "description": (
        "Atualiza parcialmente um investimento existente da carteira do usuário. "
        "Este é o método canônico para alterações parciais."
    ),
    "tags": ["Wallet"],
    "security": [{"BearerAuth": []}],
    "params": {
        "investment_id": {"description": "ID do investimento"},
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    "responses": {
        200: {"description": WALLET_UPDATE_SUCCESS_MESSAGE},
        400: {"description": "Dados inválidos"},
        401: {"description": "Token inválido"},
        404: {"description": "Investimento não encontrado"},
    },
}

WALLET_PUT_DOC: dict[str, Any] = {
    "description": (
        "Compatibilidade transitória para atualização parcial de investimento. "
        "Use `PATCH /wallet/{investment_id}` como método canônico."
    ),
    "tags": ["Wallet"],
    "security": [{"BearerAuth": []}],
    "params": {
        "investment_id": {"description": "ID do investimento"},
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    "responses": {
        200: {
            "description": WALLET_UPDATE_SUCCESS_MESSAGE,
            "headers": deprecated_headers_doc(
                successor_endpoint=WALLET_UPDATE_SUCCESSOR_ENDPOINT,
                successor_method=WALLET_UPDATE_SUCCESSOR_METHOD,
            ),
        },
        400: {"description": "Dados inválidos"},
        401: {"description": "Token inválido"},
        404: {"description": "Investimento não encontrado"},
    },
}

WALLET_DELETE_DOC: dict[str, Any] = {
    "description": "Deleta um investimento da carteira do usuário autenticado.",
    "tags": ["Wallet"],
    "security": [{"BearerAuth": []}],
    "params": {
        "investment_id": {"description": "ID do investimento"},
        "X-API-Contract": {
            "in": "header",
            "description": "Opcional. Envie 'v2' para o contrato padronizado.",
            "type": "string",
            "required": False,
        },
    },
    "responses": {
        200: {"description": "Investimento deletado com sucesso"},
        401: {"description": "Token inválido"},
        403: {"description": "Sem permissão para deletar"},
        404: {"description": "Investimento não encontrado"},
    },
}
