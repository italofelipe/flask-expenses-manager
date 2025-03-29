from functools import wraps
from typing import Any, Callable, TypeVar

import jwt
from flask import Response, current_app, jsonify, request

F = TypeVar("F", bound=Callable[..., Any])


def token_required(f: F) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Response:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"message": "Token is missing!"}), 401

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            request.user_id = payload["user_id"]  # opcional: pode injetar o ID
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token!"}), 401

        return f(*args, **kwargs)

    return decorated
