from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from flask import request
from flask_apispec.views import MethodResource

from app.auth import current_user_id, get_active_auth_context
from app.extensions.database import db
from app.models.entitlement import Entitlement
from app.schemas.entitlement_schema import EntitlementSchema
from app.services.entitlement_service import grant_entitlement, revoke_entitlement
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_success, entitlement_error_response
from .dependencies import get_entitlement_dependencies

_schema = EntitlementSchema()


def _is_admin() -> bool:
    """Return True when the JWT 'roles' claim contains 'admin'."""
    try:
        ctx = get_active_auth_context()
        return "admin" in ctx.roles
    except Exception:
        return False


class EntitlementCollectionResource(MethodResource):
    @doc(
        description="Lista os entitlements do usuário autenticado.",
        tags=["Entitlements"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Lista de entitlements"},
            401: {"description": "Token inválido"},
        },
    )
    @jwt_required()
    def get(self) -> Any:
        user_id = current_user_id()
        dependencies = get_entitlement_dependencies()
        service = dependencies.entitlement_application_service_factory(user_id)
        items = service.list_entitlements()

        return compat_success(
            legacy_payload={"items": items},
            status_code=200,
            message="Entitlements listados com sucesso",
            data={"items": items},
        )


class EntitlementCheckResource(MethodResource):
    @doc(
        description=(
            "Verifica se o usuário autenticado possui um entitlement ativo "
            "para a feature especificada. Parâmetro obrigatório: ?feature_key=xxx"
        ),
        tags=["Entitlements"],
        security=[{"BearerAuth": []}],
        params={
            "feature_key": {
                "in": "query",
                "type": "string",
                "required": True,
            }
        },
        responses={
            200: {"description": "Resultado da verificação"},
            400: {"description": "Parâmetro feature_key ausente"},
            401: {"description": "Token inválido"},
        },
    )
    @jwt_required()
    def get(self) -> Any:
        user_id = current_user_id()
        feature_key = request.args.get("feature_key", "").strip()
        if not feature_key:
            return entitlement_error_response(
                message="Parâmetro 'feature_key' é obrigatório.",
                code="MISSING_PARAMETER",
                status_code=400,
            )

        dependencies = get_entitlement_dependencies()
        service = dependencies.entitlement_application_service_factory(user_id)
        result = service.check_entitlement(feature_key)

        return compat_success(
            legacy_payload=result,
            status_code=200,
            message="Verificação de entitlement realizada",
            data=result,
        )


class AdminEntitlementGrantResource(MethodResource):
    """POST /entitlements/admin — grant an entitlement (admin only)."""

    @doc(
        description=("Concede um entitlement a um usuário. Requer role 'admin'."),
        tags=["Entitlements"],
        security=[{"BearerAuth": []}],
        responses={
            201: {"description": "Entitlement concedido"},
            400: {"description": "Parâmetros inválidos"},
            403: {"description": "Acesso negado — requer role admin"},
        },
    )
    @jwt_required()
    def post(self) -> Any:
        if not _is_admin():
            return entitlement_error_response(
                message="Admin access required",
                code="FORBIDDEN",
                status_code=403,
            )

        body: dict[str, Any] = request.get_json(silent=True) or {}
        user_id_raw: str | None = body.get("user_id")
        feature_key: str | None = body.get("feature_key")
        source: str = body.get("source", "manual")
        expires_at_raw: str | None = body.get("expires_at")

        if not user_id_raw or not feature_key:
            return entitlement_error_response(
                message="user_id and feature_key are required",
                code="VALIDATION_ERROR",
                status_code=400,
            )

        try:
            user_uuid = UUID(user_id_raw)
        except ValueError:
            return entitlement_error_response(
                message="user_id must be a valid UUID",
                code="VALIDATION_ERROR",
                status_code=400,
            )

        expires_at: datetime | None = None
        if expires_at_raw:
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
            except ValueError:
                return entitlement_error_response(
                    message="expires_at must be an ISO 8601 datetime string",
                    code="VALIDATION_ERROR",
                    status_code=400,
                )

        ent = grant_entitlement(
            user_id=user_uuid,
            feature_key=feature_key,
            source=source,
            expires_at=expires_at,
        )
        db.session.commit()
        serialized = dict(_schema.dump(ent))
        return compat_success(
            legacy_payload={"entitlement": serialized},
            status_code=201,
            message="Entitlement concedido com sucesso",
            data={"entitlement": serialized},
        )


class AdminEntitlementRevokeResource(MethodResource):
    """DELETE /entitlements/admin/<id> — revoke an entitlement by UUID (admin only)."""

    @doc(
        description=("Revoga um entitlement pelo seu UUID. Requer role 'admin'."),
        tags=["Entitlements"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Entitlement revogado"},
            403: {"description": "Acesso negado — requer role admin"},
            404: {"description": "Entitlement não encontrado"},
        },
    )
    @jwt_required()
    def delete(self, entitlement_id: UUID) -> Any:
        if not _is_admin():
            return entitlement_error_response(
                message="Admin access required",
                code="FORBIDDEN",
                status_code=403,
            )

        ent: Entitlement | None = db.session.get(Entitlement, entitlement_id)
        if ent is None:
            return entitlement_error_response(
                message="Entitlement not found",
                code="NOT_FOUND",
                status_code=404,
            )

        revoke_entitlement(ent.user_id, ent.feature_key)
        db.session.commit()
        return compat_success(
            legacy_payload={"message": "Entitlement revogado com sucesso"},
            status_code=200,
            message="Entitlement revogado com sucesso",
            data={},
        )
