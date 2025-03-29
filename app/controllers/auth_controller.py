from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User
from app.extensions.database import db
from flask_jwt_extended import create_access_token
from datetime import timedelta

login_bp = Blueprint("login", __name__, url_prefix="/login")

@login_bp.route("/register", methods=["POST"])
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
        
@login_bp.route("/auth", methods=["POST"])
def authenticate():
    data = request.get_json()
    
    if not data or not data.get("password") or not (data.get("email") or data.get("name")):
        return jsonify({"message": "Missing credentials"}), 400
    user = None
    if data.get("email"):
        user = User.query.filter_by(email=data["email"]).first()
    elif data.get("name"):
        user = User.query.filter_by(name=data["name"]).first()

    if not user or not check_password_hash(user.password, data["password"]):
        return jsonify({"message": "Invalid credentials"}), 401

    try:
        token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=1))

        return jsonify({
            "message": "Login successful",
            "token": token,
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email
            }
        }), 200

    except Exception as e:
        return jsonify({
            "message": "Login failed",
            "error": str(e)
        }), 500