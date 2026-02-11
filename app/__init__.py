import os
from uuid import uuid4

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask import Flask, Response, g
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
from app.controllers.graphql_controller import graphql_bp, register_graphql_security
from app.controllers.transaction_controller import TransactionResource, transaction_bp
from app.controllers.user_controller import UserMeResource, UserProfileResource, user_bp
from app.controllers.wallet_controller import wallet_bp
from app.docs.api_documentation import API_INFO, TAGS
from app.extensions.audit_trail import register_audit_trail
from app.extensions.database import db
from app.extensions.error_handlers import register_error_handlers
from app.middleware.cors import register_cors
from app.models.account import Account  # noqa: F401
from app.models.audit_event import AuditEvent  # noqa: F401
from app.models.credit_card import CreditCard  # noqa: F401
from app.models.investment_operation import InvestmentOperation  # noqa: F401
from app.models.tag import Tag  # noqa: F401

jwt = JWTManager()
ma = Marshmallow()


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    from config import Config, validate_security_configuration

    app.config.from_object(Config)
    runtime_database_url = os.getenv("DATABASE_URL")
    if runtime_database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = runtime_database_url

    # Carrega variáveis de ambiente com prefixo FLASK_ do .env
    app.config.from_prefixed_env()
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.getenv("MAX_REQUEST_BYTES", str(1024 * 1024))
    )
    validate_security_configuration()

    @app.before_request  # type: ignore[misc]
    def bind_request_id() -> None:
        g.request_id = uuid4().hex

    @app.after_request  # type: ignore[misc]
    def append_request_id_header(response: Response) -> Response:
        response.headers["X-Request-Id"] = str(getattr(g, "request_id", "n/a"))
        return response

    # Inicializa extensões
    db.init_app(app)
    ma.init_app(app)
    Migrate(app, db)
    jwt.init_app(app)

    # Mantem retrocompatibilidade local, mas evita create_all automatico em producao.
    auto_create_db = os.getenv("AUTO_CREATE_DB", "true").lower() == "true"
    if auto_create_db:
        with app.app_context():
            db.create_all()

    # Configuração do Swagger (OpenAPI 3.0) com documentação melhorada
    app.config.update(
        {
            "APISPEC_SPEC": APISpec(
                title=str(API_INFO["title"]),
                version=str(API_INFO["version"]),
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
    register_graphql_security(app)
    register_cors(app)
    register_audit_trail(app)

    # Registra blueprints ANTES dos endpoints no Swagger
    app.register_blueprint(transaction_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(graphql_bp)

    # Registra os endpoints documentados no Swagger
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
    from app.middleware.rate_limit import register_rate_limit_guard

    register_rate_limit_guard(app)
    register_auth_guard(app)
    register_jwt_callbacks(jwt)

    return app


__all__ = ["create_app"]
