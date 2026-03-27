from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

ContractVersion = Literal["v2", "v3", "v2_or_v3"]
JsonObject = dict[str, object]
OpenAPIDict = dict[str, object]

CONTRACT_HEADER_NAME = "X-API-Contract"
REQUEST_ID_HEADER_NAME = "X-Request-ID"
DEPRECATION_HEADER_NAME = "Deprecation"
SUNSET_HEADER_NAME = "Sunset"
WARNING_HEADER_NAME = "Warning"
SUCCESSOR_ENDPOINT_HEADER_NAME = "X-Auraxis-Successor-Endpoint"
SUCCESSOR_METHOD_HEADER_NAME = "X-Auraxis-Successor-Method"
SUCCESSOR_CONTRACT_HEADER_NAME = "X-Auraxis-Successor-Contract"
LEGACY_SUNSET_EXAMPLE = "Tue, 30 Jun 2026 23:59:59 GMT"


def contract_header_param(
    *,
    supported_version: ContractVersion = "v2_or_v3",
    description: str | None = None,
) -> OpenAPIDict:
    default_description = {
        "v2": "Opcional. Envie `v2` para o envelope padronizado.",
        "v3": "Opcional. Envie `v3` para o contrato canônico mais recente.",
        "v2_or_v3": (
            "Opcional. Envie `v2` para o envelope padronizado ou `v3` "
            "quando a rota expuser um contrato canônico específico."
        ),
    }[supported_version]
    example = {"v2": "v2", "v3": "v3", "v2_or_v3": "v3"}[supported_version]
    return {
        CONTRACT_HEADER_NAME: {
            "in": "header",
            "description": description or default_description,
            "type": "string",
            "required": False,
            "example": example,
        }
    }


def request_id_header_doc() -> OpenAPIDict:
    return {
        REQUEST_ID_HEADER_NAME: {
            "description": "Identificador único da requisição gerado pela API.",
            "schema": {"type": "string"},
            "example": "9fcd2e4f4d8747b4a7d8a2b1b930f52a",
        }
    }


def deprecated_headers_doc(
    *,
    successor_endpoint: str,
    successor_method: str | None = None,
    successor_contract: str | None = None,
    warning: str | None = None,
    sunset: str = LEGACY_SUNSET_EXAMPLE,
) -> OpenAPIDict:
    headers: OpenAPIDict = {
        DEPRECATION_HEADER_NAME: {
            "description": "Indica que a superfície atual está em deprecação.",
            "schema": {"type": "string"},
            "example": "true",
        },
        SUNSET_HEADER_NAME: {
            "description": "Data prevista para remoção da superfície legada.",
            "schema": {"type": "string"},
            "example": sunset,
        },
        SUCCESSOR_ENDPOINT_HEADER_NAME: {
            "description": "Endpoint sucessor recomendado.",
            "schema": {"type": "string"},
            "example": successor_endpoint,
        },
    }
    if successor_method is not None:
        headers[SUCCESSOR_METHOD_HEADER_NAME] = {
            "description": "Método HTTP recomendado para a superfície sucessora.",
            "schema": {"type": "string"},
            "example": successor_method,
        }
    if successor_contract is not None:
        headers[SUCCESSOR_CONTRACT_HEADER_NAME] = {
            "description": "Versão contratual recomendada para a migração.",
            "schema": {"type": "string"},
            "example": successor_contract,
        }
    if warning is not None:
        headers[WARNING_HEADER_NAME] = {
            "description": "Mensagem adicional de deprecação enviada em runtime.",
            "schema": {"type": "string"},
            "example": warning,
        }
    return headers


def json_request_body(
    *,
    schema: object,
    example: Mapping[str, object],
    description: str | None = None,
    required: bool = True,
) -> OpenAPIDict:
    payload: OpenAPIDict = {"schema": schema, "example": example}
    if description is not None:
        payload["description"] = description
    return {
        "required": required,
        "content": {"application/json": payload},
    }


def success_envelope_example(
    *,
    message: str,
    data: Mapping[str, object],
    meta: Mapping[str, object] | None = None,
) -> JsonObject:
    payload: JsonObject = {"message": message, "data": dict(data)}
    if meta is not None:
        payload["meta"] = dict(meta)
    return payload


def error_envelope_example(
    *,
    message: str,
    code: str,
    details: Mapping[str, object] | None = None,
) -> JsonObject:
    payload: JsonObject = {"message": message, "code": code}
    if details is not None:
        payload["details"] = dict(details)
    return payload


def json_success_response(
    *,
    description: str,
    message: str,
    data_example: Mapping[str, object],
    meta_example: Mapping[str, object] | None = None,
    headers: OpenAPIDict | None = None,
) -> OpenAPIDict:
    response: OpenAPIDict = {
        "description": description,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["message", "data"],
                    "properties": {
                        "message": {"type": "string"},
                        "data": {"type": "object"},
                        "meta": {"type": "object"},
                    },
                },
                "example": success_envelope_example(
                    message=message,
                    data=data_example,
                    meta=meta_example,
                ),
            }
        },
        "headers": request_id_header_doc(),
    }
    if headers is not None:
        response["headers"] = {**request_id_header_doc(), **headers}
    return response


def json_error_response(
    *,
    description: str,
    message: str,
    error_code: str,
    status_code: int,
    details_example: Mapping[str, object] | None = None,
    headers: OpenAPIDict | None = None,
) -> OpenAPIDict:
    response: OpenAPIDict = {
        "description": description,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["message", "code"],
                    "properties": {
                        "message": {"type": "string"},
                        "code": {"type": "string"},
                        "details": {"type": "object"},
                        "status_code": {"type": "integer"},
                    },
                },
                "example": {
                    **error_envelope_example(
                        message=message,
                        code=error_code,
                        details=details_example,
                    ),
                    "status_code": status_code,
                },
            }
        },
        "headers": request_id_header_doc(),
    }
    if headers is not None:
        response["headers"] = {**request_id_header_doc(), **headers}
    return response


__all__ = [
    "CONTRACT_HEADER_NAME",
    "LEGACY_SUNSET_EXAMPLE",
    "contract_header_param",
    "deprecated_headers_doc",
    "error_envelope_example",
    "json_error_response",
    "json_request_body",
    "json_success_response",
    "request_id_header_doc",
    "success_envelope_example",
]
