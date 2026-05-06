"""POST /notifications/subscribe  — register push token.
POST /notifications/unsubscribe — remove push token.
"""

from __future__ import annotations

from uuid import UUID

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.auth import get_active_auth_context
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)
from app.extensions.database import db
from app.http.request_context import current_request_id
from app.models.push_subscription import PushSubscription, PushTransport
from app.schemas.push_subscription_schema import SubscribeSchema, UnsubscribeSchema
from app.utils.datetime_utils import utc_now_naive
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import notif_error, notif_success


class PushSubscribeResource(MethodResource):
    @doc(
        summary="Registrar token de push",
        description=(
            "Registra um token de push para o dispositivo do usuário. "
            "Aceita 'expo' (FCM/APNS via Expo) e 'web_push' (VAPID). "
            "Idempotente: endpoint repetido faz upsert."
        ),
        tags=["Notificações"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        responses={
            200: json_success_response(
                description="Subscription registrada",
                message="Subscription registrada com sucesso.",
                data_example={
                    "id": "uuid",
                    "transport": "expo",
                    "endpoint": "ExponentPushToken[...]",
                },
            ),
            400: json_error_response(
                description="Dados inválidos",
                message="transport deve ser 'web_push' ou 'expo'.",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Token revogado",
                message="Token revogado.",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
        },
    )
    @jwt_required()
    @use_kwargs(SubscribeSchema(), location="json")
    def post(self, **kwargs: object) -> Response:
        user_id = UUID(get_active_auth_context().subject)

        transport = PushTransport(kwargs["transport"])
        endpoint = str(kwargs["endpoint"])
        keys = kwargs.get("keys")
        expiration_time = kwargs.get("expiration_time")
        device_label = kwargs.get("device_label")

        existing = PushSubscription.query.filter_by(
            user_id=user_id,
            transport=transport,
            endpoint=endpoint,
        ).first()

        if existing:
            existing.keys = keys
            existing.expiration_time = expiration_time
            existing.device_label = device_label
            existing.last_used_at = utc_now_naive()
            db.session.commit()
            sub = existing
        else:
            sub = PushSubscription(
                user_id=user_id,
                transport=transport,
                endpoint=endpoint,
                keys=keys,
                expiration_time=expiration_time,
                device_label=device_label,
            )
            db.session.add(sub)
            db.session.commit()

        current_app.logger.info(
            "event=push.subscribed user_id=%s transport=%s request_id=%s",
            user_id,
            transport.value,
            current_request_id(),
        )
        return notif_success(
            message="Subscription registrada com sucesso.",
            data={
                "id": str(sub.id),
                "transport": sub.transport.value,
                "endpoint": sub.endpoint,
                "device_label": sub.device_label,
            },
        )


class PushUnsubscribeResource(MethodResource):
    @doc(
        summary="Remover token de push",
        description="Remove a subscription de push para o endpoint informado.",
        tags=["Notificações"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        responses={
            200: json_success_response(
                description="Subscription removida",
                message="Subscription removida com sucesso.",
                data_example={},
            ),
            400: json_error_response(
                description="Dados inválidos",
                message="Campo 'endpoint' obrigatório.",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Token revogado",
                message="Token revogado.",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            404: json_error_response(
                description="Subscription não encontrada",
                message="Subscription não encontrada.",
                error_code="NOT_FOUND",
                status_code=404,
            ),
        },
    )
    @jwt_required()
    @use_kwargs(UnsubscribeSchema(), location="json")
    def post(self, **kwargs: object) -> Response:
        user_id = UUID(get_active_auth_context().subject)
        endpoint = str(kwargs["endpoint"])

        sub = PushSubscription.query.filter_by(
            user_id=user_id, endpoint=endpoint
        ).first()
        if not sub:
            return notif_error(
                message="Subscription não encontrada.",
                status_code=404,
                error_code="NOT_FOUND",
            )

        db.session.delete(sub)
        db.session.commit()

        current_app.logger.info(
            "event=push.unsubscribed user_id=%s request_id=%s",
            user_id,
            current_request_id(),
        )
        return notif_success(message="Subscription removida com sucesso.", data={})
