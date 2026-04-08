from __future__ import annotations

from typing import cast

from app.controllers.transaction.openapi_shared import (
    ERROR_INTERNO,
    ERROR_SEM_PERMISSAO,
    ERROR_TOKEN_INVALIDO,
    ERROR_TRANSACAO_NAO_ENCONTRADA,
    ERROR_VALIDACAO,
    TAG_TRANSACTIONS,
    TRANSACTION_CREATE_PAYLOAD_EXAMPLE,
    TRANSACTION_EXAMPLE,
    TRANSACTION_ID_PARAM,
    OpenAPIDict,
    TransactionSchema,
    contract_header_param,
    deprecated_headers_doc,
    json_error_response,
    json_request_body,
    json_success_response,
)

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
            description=ERROR_VALIDACAO,
            message=ERROR_VALIDACAO,
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
            description=ERROR_VALIDACAO,
            message=ERROR_VALIDACAO,
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

__all__ = [
    "TRANSACTION_CREATE_DOC",
    "TRANSACTION_UPDATE_PATCH_DOC",
    "TRANSACTION_UPDATE_PUT_COMPAT_DOC",
    "TRANSACTION_UPDATE_DOC",
    "TRANSACTION_SOFT_DELETE_DOC",
    "TRANSACTION_RESTORE_DOC",
    "TRANSACTION_FORCE_DELETE_DOC",
]
