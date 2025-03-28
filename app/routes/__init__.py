from flask import Blueprint

# centralizador geral
app_bp = Blueprint("app", __name__)

# importa e registra cada módulo de rota
from app.routes.login_route import login_bp
app_bp.register_blueprint(login_bp)

# você pode adicionar outras rotas:
# from app.routes.user.route import user_bp
# app_bp.register_blueprint(user_bp)