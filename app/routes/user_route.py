from flask import Blueprint, jsonify
from app.middleware.jwt import token_required

user_bp = Blueprint("user", __name__, url_prefix="/user")

@user_bp.route("/me", methods=["GET"])
@token_required
def me():
    return jsonify({"message": "Token válido!", "user_id": request.user_id})