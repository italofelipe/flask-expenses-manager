"""Shared entries and invitations REST resources — J13."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request

from app.auth import current_user_id
from app.controllers.response_contract import ResponseContractError
from app.exceptions import ValidationAPIError
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import shared_entries_bp
from .contracts import api_error_tuple, compat_success, contract_error_tuple
from .dependencies import get_shared_entries_dependencies
from .serializers import (
    serialize_invitation,
    serialize_shared_entry,
    serialize_shared_entry_with_me,
)
from .validators import (
    _parse_create_invitation_payload,
    _parse_create_shared_entry_payload,
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
    serialized = [serialize_shared_entry_with_me(entry, user_id) for entry in entries]
    return compat_success(
        legacy_payload={"shared_entries": serialized},
        status_code=200,
        message="Compartilhamentos recebidos listados com sucesso",
        data={"shared_entries": serialized},
    )


@shared_entries_bp.route("/<uuid:shared_entry_id>", methods=["PATCH"])
@jwt_required()
def update_shared_entry_route(shared_entry_id: UUID) -> tuple[dict[str, Any], int]:
    """Update a shared entry with optimistic locking.

    Request body must include ``version`` (current known version) to guard
    against concurrent modifications.  Returns HTTP 409 if the version does
    not match the DB state.
    """
    from app.services.shared_entry_service import (
        SharedEntryConcurrentEditError,
        SharedEntryForbiddenError,
        SharedEntryNotFoundError,
    )

    user_id: UUID = current_user_id()
    payload = request.get_json(silent=True) or {}

    if "version" not in payload:
        raise ResponseContractError(
            "Campo 'version' é obrigatório para atualização.",
            code="VALIDATION_ERROR",
            status_code=400,
            details={"version": ["required"]},
            legacy_payload={"error": "Campo 'version' é obrigatório para atualização."},
        )
    try:
        expected_version = int(payload["version"])
    except (TypeError, ValueError) as exc:
        raise ResponseContractError(
            "Campo 'version' deve ser um inteiro.",
            code="VALIDATION_ERROR",
            status_code=400,
            details={"version": ["must_be_integer"]},
            legacy_payload={"error": "Campo 'version' deve ser um inteiro."},
        ) from exc

    split_type: str | None = payload.get("split_type")
    if split_type is not None:
        valid_split_types = {
            item.value
            for item in __import__(
                "app.models.shared_entry", fromlist=["SplitType"]
            ).SplitType
        }
        if split_type not in valid_split_types:
            raise ResponseContractError(
                "Campo 'split_type' inválido.",
                code="VALIDATION_ERROR",
                status_code=400,
                details={"split_type": ["must_be_one_of: equal, percentage, custom"]},
                legacy_payload={"error": "Campo 'split_type' inválido."},
            )

    try:
        entry = get_shared_entries_dependencies().update_shared_entry(
            shared_entry_id,
            user_id,
            expected_version=expected_version,
            split_type=split_type,
        )
    except ResponseContractError as exc:
        return contract_error_tuple(exc)
    except SharedEntryNotFoundError as exc:
        return api_error_tuple(exc)
    except SharedEntryForbiddenError as exc:
        return api_error_tuple(exc)
    except SharedEntryConcurrentEditError as exc:
        return api_error_tuple(exc)

    serialized = serialize_shared_entry(entry)
    return compat_success(
        legacy_payload={"shared_entry": serialized},
        status_code=200,
        message="Compartilhamento atualizado com sucesso",
        data={"shared_entry": serialized},
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
