from functools import wraps
from typing import Any, Callable, TypeVar, cast

import jwt
from flask import Response, current_app, jsonify, request

F = TypeVar("F", bound=Callable[..., Any])
JSON_MIMETYPE = "application/json"


def token_required(f: F) -> F:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return Response(
                jsonify({"message": "Token is missing!"}).get_data(),
                status=401,
                mimetype=JSON_MIMETYPE,
            )

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            request.environ["auraxis.user_id"] = str(payload.get("user_id", ""))
        except jwt.ExpiredSignatureError:
            return Response(
                jsonify({"message": "Token expired!"}).get_data(),
                status=401,
                mimetype=JSON_MIMETYPE,
            )
        except jwt.InvalidTokenError:
            return Response(
                jsonify({"message": "Invalid token!"}).get_data(),
                status=401,
                mimetype=JSON_MIMETYPE,
            )

        return f(*args, **kwargs)

    return cast(F, decorated)
