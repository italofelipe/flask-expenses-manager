from __future__ import annotations

from flask import Response
from flask_apispec.views import MethodResource
from flask_jwt_extended import unset_jwt_cookies

from app.auth import current_user_id
from app.docs.openapi_helpers import (
    contract_header_param,
    json_success_response,
)
from app.extensions.database import db
from app.extensions.jwt_revocation_cache import get_jwt_revocation_cache
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_success
from .dependencies import get_auth_dependencies


class LogoutResource(MethodResource):
    @doc(
        summary="Revogar sessão atual",
        description=(
            "Revoga o JWT atual do usuário autenticado.\n\n"
            "Depois dessa chamada, o token utilizado deixa de ser aceito nas "
            "rotas protegidas."
        ),
        tags=["Autenticação"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        responses={
            200: json_success_response(
                description="Logout realizado com sucesso",
                message="Logout successful",
                data_example={},
            ),
        },
    )
    @jwt_required()
    def post(self) -> Response:
        dependencies = get_auth_dependencies()
        identity = current_user_id()
        user = dependencies.get_user_by_id(identity)
        if user:
            # SEC-GAP-01 — invalidate both the access JTI and the refresh JTI
            # so a leaked refresh cookie cannot be reused after logout.
            user.current_jti = None
            user.refresh_token_jti = None
            db.session.commit()
            get_jwt_revocation_cache().invalidate(str(identity))
        response = compat_success(
            legacy_payload={"message": "Logout successful"},
            status_code=200,
            message="Logout successful",
            data={},
        )
        # SEC-GAP-01 — clear the httpOnly refresh cookie on the client.
        unset_jwt_cookies(response)
        return response
