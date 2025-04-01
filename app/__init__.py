from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask import Flask
from flask_apispec import FlaskApiSpec
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate

from app.controllers import all_routes
from app.controllers.auth_controller import (
    AuthResource,
    LogoutResource,
    RegisterResource,
)
from app.controllers.transaction_controller import TransactionResource
from app.controllers.user_controller import UserProfileResource
from app.extensions.database import db
from app.extensions.error_handlers import register_error_handlers
from app.models.account import Account  # type: ignore
from app.models.credit_card import CreditCard  # type: ignore
from app.models.tag import Tag  # type: ignore

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

    # Configuração do Swagger (OpenAPI 3.0)
    app.config.update(
        {
            "APISPEC_SPEC": APISpec(
                title="Not Enough Cash, Stranger!",
                version="1.0.0",
                openapi_version="3.0.2",
                plugins=[MarshmallowPlugin()],
                components={
                    "securitySchemes": {
                        "BearerAuth": {
                            "type": "http",
                            "scheme": "bearer",
                            "bearerFormat": "JWT",
                        }
                    }
                },
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
    for route in all_routes:
        app.register_blueprint(route)

    # ✅ Registra os endpoints documentados no Swagger
    docs.register(RegisterResource, blueprint="auth", endpoint="registerresource")
    docs.register(AuthResource, blueprint="auth", endpoint="authresource")
    docs.register(UserProfileResource, blueprint="user", endpoint="profile")
    docs.register(LogoutResource, blueprint="auth", endpoint="logoutresource")
    docs.register(
        TransactionResource, blueprint="transaction", endpoint="transactionresource"
    )
    from app.extensions.jwt_callbacks import register_jwt_callbacks
    from app.middleware.auth_guard import register_auth_guard

    register_auth_guard(app)
    register_jwt_callbacks(jwt)

    return app
