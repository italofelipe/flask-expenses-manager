import jwt
from functools import wraps
from flask import request, jsonify, current_app

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"message": "Token is missing!"}), 401

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            request.user_id = payload["user_id"]  # opcional: pode injetar o ID
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token!"}), 401

        return f(*args, **kwargs)
    return decorated