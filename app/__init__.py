from flask import Flask
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate

from app.controllers import all_routes
from app.extensions.database import db
from app.extensions.error_handlers import register_error_handlers

jwt = JWTManager()
ma = Marshmallow()


def create_app() -> Flask:
    print("Creating Flask app")

    app = Flask(__name__, instance_relative_config=True)
    from config import Config

    app.config.from_object(Config)

    # Carrega variáveis de ambiente com prefixo FLASK_ do .env
    app.config.from_prefixed_env()

    # Inicializa extensões
    db.init_app(app)
    ma.init_app(app)
    Migrate(app, db)
    jwt.init_app(app)
    register_error_handlers(app)

    # Registra blueprints
    for route in all_routes:
        app.register_blueprint(route)

    # Debug das configurações JWT
    print("JWT config loaded:")
    print("  JWT_SECRET_KEY:", app.config.get("JWT_SECRET_KEY"))
    print("  JWT_TOKEN_LOCATION:", app.config.get("JWT_TOKEN_LOCATION"))
    print("  JWT_HEADER_TYPE:", app.config.get("JWT_HEADER_TYPE"))

    return app
