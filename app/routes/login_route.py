from flask import Blueprint, request, jsonify
from app.models import User
from app import db

login_bp = Blueprint("login", __name__, url_prefix="/login")

@login_bp.route("", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not all(key in data for key in ["name", "email", "password"]):
        return jsonify({"message": "Missing required fields"}), 400

    try:
        user = User(
            name=data["name"],
            email=data["email"],
            password=data["password"]
        )
        db.session.add(user)
        db.session.commit()

        return jsonify({
            "message": "User created successfully",
            "data": {
                "id": user.id,
                "name": user.name,
                "email": user.email
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "message": "Failed to create user",
            "error": str(e)
        }), 500