from flask import Blueprint

from .auth_controller import login_bp
from .transaction_controller import transaction_bp
from .user_controller import user_bp

# centralizador geral
app_bp = Blueprint("app", __name__)

all_routes = [login_bp, user_bp, transaction_bp]
