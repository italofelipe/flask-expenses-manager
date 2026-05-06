"""POST /user/me/avatar  — upload avatar to S3.
DELETE /user/me/avatar  — remove avatar.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response, current_app, request
from flask_apispec.views import MethodResource

from app.auth import get_active_auth_context
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)
from app.extensions.database import db
from app.http.request_context import current_request_id
from app.services.avatar_storage import (
    AvatarStorageError,
    AvatarValidationError,
    delete_avatar_by_url,
    upload_avatar,
    validate_avatar_file,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_error, compat_success
from .dependencies import get_user_dependencies


class AvatarResource(MethodResource):
    @doc(
        summary="Upload avatar do usuário",
        description=(
            "Recebe uma imagem (JPEG, PNG ou WebP, máx. 5 MB) via multipart/form-data "
            "e armazena no S3. Retorna a URL pública do avatar atualizado."
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        requestBody={
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {"file": {"type": "string", "format": "binary"}},
                        "required": ["file"],
                    }
                }
            },
        },
        responses={
            200: json_success_response(
                description="Avatar atualizado com sucesso",
                message="Avatar atualizado com sucesso.",
                data_example={"avatar_url": "https://cdn.auraxis.com.br/avatars/..."},
            ),
            400: json_error_response(
                description="Arquivo inválido",
                message="Tipo de arquivo não permitido.",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Token revogado",
                message="Token revogado.",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            500: json_error_response(
                description="Falha no storage",
                message="Falha ao armazenar avatar.",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @jwt_required()
    def post(self) -> Response:
        user = self._get_user_or_error()
        if isinstance(user, Response):
            return user

        if "file" not in request.files:
            return compat_error(
                legacy_payload={"message": "Campo 'file' ausente no form."},
                status_code=400,
                message="Campo 'file' ausente no form.",
                error_code="VALIDATION_ERROR",
            )

        file = request.files["file"]
        if not file.filename:
            return compat_error(
                legacy_payload={"message": "Nenhum arquivo enviado."},
                status_code=400,
                message="Nenhum arquivo enviado.",
                error_code="VALIDATION_ERROR",
            )

        try:
            ext = validate_avatar_file(
                file.stream,
                file.content_type or "",
                file.filename,
            )
        except AvatarValidationError as exc:
            return compat_error(
                legacy_payload={"message": str(exc)},
                status_code=400,
                message=str(exc),
                error_code="VALIDATION_ERROR",
            )

        old_url = user.avatar_url

        try:
            avatar_url = upload_avatar(
                user_id=str(user.id),
                file_stream=file.stream,
                content_type=file.content_type or "application/octet-stream",
                ext=ext,
            )
        except AvatarStorageError as exc:
            current_app.logger.error(
                "event=avatar.upload_failed user_id=%s request_id=%s error=%s",
                user.id,
                current_request_id(),
                exc,
            )
            return compat_error(
                legacy_payload={"message": "Falha ao armazenar avatar."},
                status_code=500,
                message="Falha ao armazenar avatar.",
                error_code="INTERNAL_ERROR",
            )

        user.avatar_url = avatar_url
        db.session.commit()

        if old_url:
            delete_avatar_by_url(old_url)

        current_app.logger.info(
            "event=avatar.uploaded user_id=%s request_id=%s",
            user.id,
            current_request_id(),
        )
        return compat_success(
            legacy_payload={
                "message": "Avatar atualizado com sucesso.",
                "data": {"avatar_url": avatar_url},
            },
            status_code=200,
            message="Avatar atualizado com sucesso.",
            data={"avatar_url": avatar_url},
        )

    @doc(
        summary="Remover avatar do usuário",
        description="Remove o avatar do usuário autenticado e deleta o arquivo do S3.",
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        responses={
            200: json_success_response(
                description="Avatar removido com sucesso",
                message="Avatar removido com sucesso.",
                data_example={},
            ),
            401: json_error_response(
                description="Token revogado",
                message="Token revogado.",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            404: json_error_response(
                description="Nenhum avatar configurado",
                message="Nenhum avatar configurado.",
                error_code="NOT_FOUND",
                status_code=404,
            ),
        },
    )
    @jwt_required()
    def delete(self) -> Response:
        user = self._get_user_or_error()
        if isinstance(user, Response):
            return user

        if not user.avatar_url:
            return compat_error(
                legacy_payload={"message": "Nenhum avatar configurado."},
                status_code=404,
                message="Nenhum avatar configurado.",
                error_code="NOT_FOUND",
            )

        old_url = user.avatar_url
        user.avatar_url = None
        db.session.commit()

        delete_avatar_by_url(old_url)

        current_app.logger.info(
            "event=avatar.deleted user_id=%s request_id=%s",
            user.id,
            current_request_id(),
        )
        return compat_success(
            legacy_payload={"message": "Avatar removido com sucesso."},
            status_code=200,
            message="Avatar removido com sucesso.",
            data={},
        )

    @staticmethod
    def _get_user_or_error() -> Any:
        auth_context = get_active_auth_context()
        dependencies = get_user_dependencies()
        user = dependencies.get_user_by_id(UUID(auth_context.subject))
        if not user:
            return compat_error(
                legacy_payload={"message": "Usuário não encontrado."},
                status_code=404,
                message="Usuário não encontrado.",
                error_code="NOT_FOUND",
            )
        if (
            auth_context.jti is None
            or not hasattr(user, "current_jti")
            or user.current_jti != auth_context.jti
        ):
            return compat_error(
                legacy_payload={"message": "Token revogado."},
                status_code=401,
                message="Token revogado.",
                error_code="UNAUTHORIZED",
            )
        return user
