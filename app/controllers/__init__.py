from flask import Blueprint

# centralizador geral
app_bp = Blueprint("app", __name__)

from .auth_controller import login_bp
from .user_controller import user_bp

all_routes = [login_bp, user_bp]