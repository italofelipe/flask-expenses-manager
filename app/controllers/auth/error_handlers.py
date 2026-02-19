from __future__ import annotations

from typing import Any

from flask import abort, jsonify, make_response
from webargs import ValidationError as WebargsValidationError
from webargs.flaskparser import parser

from app.utils.response_builder import error_payload

from .contracts import is_v2_contract


@parser.error_handler
def handle_webargs_error(
    err: WebargsValidationError,
    req: Any,
    schema: Any = None,
    *,
    error_status_code: Any = None,
    error_headers: Any = None,
    **kwargs: Any,
) -> Any:
    """
    Converte erros de validação (422) do Webargs/Marshmallow em uma
    resposta JSON 400 mais amigável para o cliente.
    """
    error_message = "Validation error"
    if "password" in err.messages:
        error_message = (
            "Senha inválida: não atende aos critérios mínimos de segurança "
            "(mín. 10 caracteres, 1 letra maiúscula, 1 número e 1 símbolo)."
        )

    payload: dict[str, Any] = {
        "message": error_message,
        "errors": err.messages,
    }
    if is_v2_contract():
        payload = error_payload(
            message=error_message,
            code="VALIDATION_ERROR",
            details={"errors": err.messages},
        )

    resp = make_response(jsonify(payload), 400)
    abort(resp)
    raise AssertionError
