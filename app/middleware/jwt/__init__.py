from functools import wraps
from typing import Any, Callable, TypeVar, cast

import jwt
from flask import Response, current_app, request

from app.utils.api_contract import is_v2_contract_request
from app.utils.response_builder import error_payload, json_response

F = TypeVar("F", bound=Callable[..., Any])


def _legacy_error_payload(message: str) -> dict[str, str]:
    return {"message": message}


def _token_error_response(message: str) -> Response:
    payload: dict[str, Any] = _legacy_error_payload(message)
    if is_v2_contract_request():
        payload = error_payload(message=message, code="UNAUTHORIZED", details={})
    return json_response(payload, status_code=401)


def token_required(f: F) -> F:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return _token_error_response("Token is missing!")

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            request.environ["auraxis.user_id"] = str(payload.get("user_id", ""))
        except jwt.ExpiredSignatureError:
            return _token_error_response("Token expired!")
        except jwt.InvalidTokenError:
            return _token_error_response("Invalid token!")

        return f(*args, **kwargs)

    return cast(F, decorated)
