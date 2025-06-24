from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask import Flask
from flask_apispec import FlaskApiSpec
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate

from app.controllers.auth_controller import (
    AuthResource,
    LogoutResource,
    RegisterResource,
    auth_bp,
)
from app.controllers.ticker_controller import ticker_bp
from app.controllers.transaction_controller import TransactionResource, transaction_bp
from app.controllers.user_controller import UserMeResource, UserProfileResource, user_bp
from app.docs.api_documentation import API_INFO, TAGS
from app.extensions.database import db
from app.extensions.error_handlers import register_error_handlers
from app.models.account import Account  # noqa: F401
from app.models.credit_card import CreditCard  # noqa: F401
from app.models.tag import Tag  # noqa: F401

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

    # Cria todas as tabelas no banco de dados (apenas para ambiente de desenvolvimento)
    with app.app_context():
        db.create_all()

    # Configuração do Swagger (OpenAPI 3.0) com documentação melhorada
    app.config.update(
        {
            "APISPEC_SPEC": APISpec(
                title=API_INFO["title"],
                version=API_INFO["version"],
                openapi_version="3.0.2",
                plugins=[MarshmallowPlugin()],
                info={
                    "description": API_INFO["description"],
                    "contact": API_INFO["contact"],
                    "license": API_INFO["license"],
                },
                components={
                    "securitySchemes": {
                        "BearerAuth": {
                            "type": "http",
                            "scheme": "bearer",
                            "bearerFormat": "JWT",
                            "description": "Token JWT obtido através do login",
                        }
                    }
                },
                tags=TAGS,
            ),
            "APISPEC_SWAGGER_URL": "/docs/swagger/",  # JSON da spec
            "APISPEC_SWAGGER_UI_URL": "/docs/",  # Swagger UI
            "APISPEC_OPTIONS": {"security": [{"BearerAuth": []}]},
        }
    )

    docs = FlaskApiSpec(app)

    # Registra erros globais
    register_error_handlers(app)

    # ✅ Registra blueprints ANTES dos endpoints no Swagger
    app.register_blueprint(transaction_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(ticker_bp)

    # ✅ Registra os endpoints documentados no Swagger
    docs.register(RegisterResource, blueprint="auth", endpoint="registerresource")
    docs.register(AuthResource, blueprint="auth", endpoint="authresource")
    docs.register(UserProfileResource, blueprint="user", endpoint="profile")
    docs.register(UserMeResource, blueprint="user", endpoint="me")
    docs.register(LogoutResource, blueprint="auth", endpoint="logoutresource")
    docs.register(
        TransactionResource, blueprint="transaction", endpoint="transactionresource"
    )
    from app.extensions.jwt_callbacks import register_jwt_callbacks
    from app.middleware.auth_guard import register_auth_guard

    register_auth_guard(app)
    register_jwt_callbacks(jwt)

    return app


__all__ = ["create_app"]
