from __future__ import annotations

from flask import Response
from flask_apispec.views import MethodResource

from app.auth import current_user_id
from app.extensions.database import db
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_success
from .dependencies import get_auth_dependencies


class LogoutResource(MethodResource):
    @doc(
        description="Revoga o token JWT atual (logout do usuário)",
        tags=["Autenticação"],
        security=[{"BearerAuth": []}],
        params={
            "X-API-Contract": {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            }
        },
        responses={
            200: {"description": "Logout realizado com sucesso"},
        },
    )
    @jwt_required()
    def post(self) -> Response:
        dependencies = get_auth_dependencies()
        identity = current_user_id()
        user = dependencies.get_user_by_id(identity)
        if user:
            user.current_jti = None
            db.session.commit()
        return compat_success(
            legacy_payload={"message": "Logout successful"},
            status_code=200,
            message="Logout successful",
            data={},
        )
