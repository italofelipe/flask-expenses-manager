"""Shared entries and invitations REST resources — J13."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from flask import request

from app.auth import current_user_id
from app.controllers.response_contract import ResponseContractError
from app.exceptions import ValidationAPIError
from app.models.shared_entry import SplitType
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import shared_entries_bp
from .contracts import api_error_tuple, compat_success, contract_error_tuple
from .dependencies import get_shared_entries_dependencies
from .serializers import serialize_invitation, serialize_shared_entry

INVALID_EXPIRES_IN_HOURS_MESSAGE = "Campo 'expires_in_hours' inválido."


@dataclass(frozen=True)
class CreateSharedEntryInput:
    transaction_id: UUID
    split_type: str


@dataclass(frozen=True)
class CreateInvitationInput:
    shared_entry_id: UUID
    invitee_email: str
    split_value: float | None
    share_amount: float | None
    message: str | None
    expires_in_hours: int


def _parse_uuid_field(
    payload: dict[str, object],
    field_name: str,
) -> UUID:
    raw_value = payload.get(field_name)
    if raw_value in (None, ""):
        raise ValidationAPIError(
            message=f"{field_name} é obrigatório.",
            details={field_name: ["required"]},
        )
    try:
        return UUID(str(raw_value))
    except (ValueError, AttributeError) as exc:
        raise ValidationAPIError(
            message=f"{field_name} inválido.",
            details={field_name: ["invalid_uuid"]},
        ) from exc


def _parse_decimal_field(
    payload: dict[str, object],
    field_name: str,
) -> float | None:
    raw_value = payload.get(field_name)
    if raw_value in (None, ""):
        return None
    try:
        return float(Decimal(str(raw_value)))
    except (InvalidOperation, ValueError) as exc:
        raise ResponseContractError(
            f"Campo '{field_name}' inválido.",
            code="VALIDATION_ERROR",
            status_code=400,
            details={field_name: ["must_be_number"]},
            legacy_payload={"error": f"Campo '{field_name}' inválido."},
        ) from exc


def _parse_expires_in_hours(payload: dict[str, object]) -> int:
    raw_value = payload.get("expires_in_hours", 48)
    try:
        value = int(str(raw_value))
    except (TypeError, ValueError) as exc:
        raise ResponseContractError(
            INVALID_EXPIRES_IN_HOURS_MESSAGE,
            code="VALIDATION_ERROR",
            status_code=400,
            details={"expires_in_hours": ["must_be_integer"]},
            legacy_payload={"error": INVALID_EXPIRES_IN_HOURS_MESSAGE},
        ) from exc
    if value <= 0:
        raise ResponseContractError(
            INVALID_EXPIRES_IN_HOURS_MESSAGE,
            code="VALIDATION_ERROR",
            status_code=400,
            details={"expires_in_hours": ["must_be_positive"]},
            legacy_payload={"error": INVALID_EXPIRES_IN_HOURS_MESSAGE},
        )
    return value


def _parse_create_shared_entry_payload(payload: object) -> CreateSharedEntryInput:
    if not isinstance(payload, dict):
        payload = {}
    split_type_raw = payload.get("split_type")
    missing_fields: dict[str, list[str]] = {}
    if payload.get("transaction_id") in (None, ""):
        missing_fields["transaction_id"] = ["required"]
    if not isinstance(split_type_raw, str) or not split_type_raw:
        missing_fields["split_type"] = ["required"]
    if missing_fields:
        raise ValidationAPIError(
            message="transaction_id e split_type são obrigatórios.",
            details=missing_fields,
        )
    transaction_id = _parse_uuid_field(payload, "transaction_id")
    valid_split_types = {item.value for item in SplitType}
    if split_type_raw not in valid_split_types:
        raise ResponseContractError(
            "Campo 'split_type' inválido.",
            code="VALIDATION_ERROR",
            status_code=400,
            details={"split_type": ["must_be_one_of: equal, percentage, fixed"]},
            legacy_payload={"error": "Campo 'split_type' inválido."},
        )
    return CreateSharedEntryInput(
        transaction_id=transaction_id,
        split_type=split_type_raw,
    )


def _parse_create_invitation_payload(payload: object) -> CreateInvitationInput:
    if not isinstance(payload, dict):
        payload = {}
    invitee_email = payload.get("invitee_email")
    missing_fields: dict[str, list[str]] = {}
    if payload.get("shared_entry_id") in (None, ""):
        missing_fields["shared_entry_id"] = ["required"]
    if not isinstance(invitee_email, str) or not invitee_email:
        missing_fields["invitee_email"] = ["required"]
    if missing_fields:
        raise ValidationAPIError(
            message="shared_entry_id e invitee_email são obrigatórios.",
            details=missing_fields,
        )
    assert isinstance(invitee_email, str)
    shared_entry_id = _parse_uuid_field(payload, "shared_entry_id")
    message = payload.get("message")
    if message is not None and not isinstance(message, str):
        raise ResponseContractError(
            "Campo 'message' inválido.",
            code="VALIDATION_ERROR",
            status_code=400,
            details={"message": ["must_be_string"]},
            legacy_payload={"error": "Campo 'message' inválido."},
        )
    return CreateInvitationInput(
        shared_entry_id=shared_entry_id,
        invitee_email=invitee_email,
        split_value=_parse_decimal_field(payload, "split_value"),
        share_amount=_parse_decimal_field(payload, "share_amount"),
        message=message,
        expires_in_hours=_parse_expires_in_hours(payload),
    )


# ---------------------------------------------------------------------------
# Shared entries endpoints
# ---------------------------------------------------------------------------


@shared_entries_bp.route("", methods=["POST"])
@jwt_required()
def create_shared_entry() -> tuple[dict[str, Any], int]:
    """Share a transaction entry."""
    from app.services.shared_entry_service import (
        SharedEntryForbiddenError,
        SharedEntryNotFoundError,
    )

    user_id: UUID = current_user_id()
    try:
        parsed = _parse_create_shared_entry_payload(request.get_json(silent=True))
        entry = get_shared_entries_dependencies().share_entry(
            user_id,
            parsed.transaction_id,
            parsed.split_type,
        )
    except ResponseContractError as exc:
        return contract_error_tuple(exc)
    except ValidationAPIError as exc:
        return api_error_tuple(exc)
    except (SharedEntryNotFoundError, SharedEntryForbiddenError) as exc:
        return api_error_tuple(exc)

    serialized = serialize_shared_entry(entry)
    return compat_success(
        legacy_payload={"shared_entry": serialized},
        status_code=201,
        message="Compartilhamento criado com sucesso",
        data={"shared_entry": serialized},
    )


@shared_entries_bp.route("/by-me", methods=["GET"])
@jwt_required()
def list_shared_by_me() -> tuple[dict[str, Any], int]:
    """List all shared entries I own."""
    user_id: UUID = current_user_id()
    entries = get_shared_entries_dependencies().list_shared_by_me(user_id)
    serialized = [serialize_shared_entry(entry) for entry in entries]
    return compat_success(
        legacy_payload={"shared_entries": serialized},
        status_code=200,
        message="Compartilhamentos listados com sucesso",
        data={"shared_entries": serialized},
    )


@shared_entries_bp.route("/with-me", methods=["GET"])
@jwt_required()
def list_shared_with_me() -> tuple[dict[str, Any], int]:
    """List all shared entries where I am an accepted invitee."""
    user_id: UUID = current_user_id()
    entries = get_shared_entries_dependencies().list_shared_with_me(user_id)
    serialized = [serialize_shared_entry(entry) for entry in entries]
    return compat_success(
        legacy_payload={"shared_entries": serialized},
        status_code=200,
        message="Compartilhamentos recebidos listados com sucesso",
        data={"shared_entries": serialized},
    )


@shared_entries_bp.route("/<uuid:shared_entry_id>", methods=["DELETE"])
@jwt_required()
def revoke_shared_entry(shared_entry_id: UUID) -> tuple[dict[str, Any], int]:
    """Revoke a shared entry."""
    from app.services.shared_entry_service import (
        SharedEntryAlreadyRevokedError,
        SharedEntryForbiddenError,
        SharedEntryNotFoundError,
    )

    user_id: UUID = current_user_id()
    try:
        entry = get_shared_entries_dependencies().revoke_share(
            shared_entry_id,
            user_id,
        )
    except SharedEntryNotFoundError as exc:
        return api_error_tuple(exc)
    except SharedEntryForbiddenError as exc:
        return api_error_tuple(exc)
    except SharedEntryAlreadyRevokedError as exc:
        return api_error_tuple(exc)

    serialized = serialize_shared_entry(entry)
    return compat_success(
        legacy_payload={"shared_entry": serialized},
        status_code=200,
        message="Compartilhamento revogado com sucesso",
        data={"shared_entry": serialized},
    )


# ---------------------------------------------------------------------------
# Invitation endpoints
# ---------------------------------------------------------------------------


@shared_entries_bp.route("/invitations", methods=["GET"])
@jwt_required()
def list_invitations() -> tuple[dict[str, Any], int]:
    """List all invitations I created."""
    user_id: UUID = current_user_id()
    invitations = get_shared_entries_dependencies().list_invitations(user_id)
    serialized = [serialize_invitation(invitation) for invitation in invitations]
    return compat_success(
        legacy_payload={"invitations": serialized},
        status_code=200,
        message="Convites listados com sucesso",
        data={"invitations": serialized},
    )


@shared_entries_bp.route("/invitations", methods=["POST"])
@jwt_required()
def create_invitation() -> tuple[dict[str, Any], int]:
    """Create an invitation for a shared entry."""
    from app.services.invitation_service import (
        InvitationOwnershipError,
        SharedEntryNotFoundError,
    )

    user_id: UUID = current_user_id()
    try:
        parsed = _parse_create_invitation_payload(request.get_json(silent=True))
        invitation = get_shared_entries_dependencies().create_invitation(
            user_id,
            parsed.shared_entry_id,
            parsed.invitee_email,
            parsed.split_value,
            parsed.share_amount,
            parsed.message,
            parsed.expires_in_hours,
        )
    except ResponseContractError as exc:
        return contract_error_tuple(exc)
    except ValidationAPIError as exc:
        return api_error_tuple(exc)
    except (SharedEntryNotFoundError, InvitationOwnershipError) as exc:
        return api_error_tuple(exc)

    serialized = serialize_invitation(invitation)
    return compat_success(
        legacy_payload={"invitation": serialized},
        status_code=201,
        message="Convite criado com sucesso",
        data={"invitation": serialized},
    )


@shared_entries_bp.route("/invitations/<string:token>/accept", methods=["POST"])
@jwt_required()
def accept_invitation(token: str) -> tuple[dict[str, Any], int]:
    """Accept an invitation by its token."""
    from app.services.invitation_service import (
        InvitationAlreadyProcessedError,
        InvitationExpiredError,
        InvitationNotFoundError,
    )

    user_id: UUID = current_user_id()
    try:
        invitation = get_shared_entries_dependencies().accept_invitation(
            token,
            user_id,
        )
    except InvitationExpiredError as exc:
        return api_error_tuple(exc)
    except InvitationNotFoundError as exc:
        return api_error_tuple(exc)
    except InvitationAlreadyProcessedError as exc:
        return api_error_tuple(exc)

    serialized = serialize_invitation(invitation)
    return compat_success(
        legacy_payload={"invitation": serialized},
        status_code=200,
        message="Convite aceito com sucesso",
        data={"invitation": serialized},
    )


@shared_entries_bp.route("/invitations/<uuid:invitation_id>", methods=["DELETE"])
@jwt_required()
def revoke_invitation(invitation_id: UUID) -> tuple[dict[str, Any], int]:
    """Revoke a pending invitation."""
    from app.services.invitation_service import (
        InvitationAlreadyProcessedError,
        InvitationForbiddenError,
        InvitationNotFoundError,
    )

    user_id: UUID = current_user_id()
    try:
        invitation = get_shared_entries_dependencies().revoke_invitation(
            invitation_id,
            user_id,
        )
    except InvitationNotFoundError as exc:
        return api_error_tuple(exc)
    except InvitationForbiddenError as exc:
        return api_error_tuple(exc)
    except InvitationAlreadyProcessedError as exc:
        return api_error_tuple(exc)

    serialized = serialize_invitation(invitation)
    return compat_success(
        legacy_payload={"invitation": serialized},
        status_code=200,
        message="Convite revogado com sucesso",
        data={"invitation": serialized},
    )
