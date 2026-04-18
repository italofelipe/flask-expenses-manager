"""Input parsing and validation helpers for the shared entries domain."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.controllers.response_contract import ResponseContractError
from app.exceptions import ValidationAPIError
from app.models.shared_entry import SplitType

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
            details={"split_type": ["must_be_one_of: equal, percentage, custom"]},
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
