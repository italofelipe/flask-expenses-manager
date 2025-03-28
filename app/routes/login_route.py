from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from app.models import User
from app import db

login_bp = Blueprint("login", __name__, url_prefix="/login")

@login_bp.route("", methods=["POST"])
def register():
    data = request.get_json()

    # Validação mínima
    required_fields = ["name", "email", "password"]
    if not data or not all(field in data for field in required_fields):
        return jsonify({
            "message": "Missing required fields",
            "data": None
        }), 400

    try:
        # Verifica se o e-mail já existe
        if User.query.filter_by(email=data["email"]).first():
            return jsonify({
                "message": "Email already registered",
                "data": None
            }), 409

        # Criptografa a senha
        hashed_password = generate_password_hash(data["password"])

        # Cria novo usuário
        user = User(
            name=data["name"],
            email=data["email"],
            password=hashed_password
        )
        db.session.add(user)
        db.session.flush()
        print(user.id)
        db.session.commit()

        return jsonify({
            "message": "User created successfully",
            "data": {
                "id": str(user.id),
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