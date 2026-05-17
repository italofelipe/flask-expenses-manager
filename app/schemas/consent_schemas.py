"""Marshmallow schemas for the LGPD versioned consent endpoints (#1259)."""

from __future__ import annotations

from marshmallow import Schema, fields, validate

from app.models.consent import ConsentAction, ConsentKind, ConsentSource

_KIND_CHOICES = tuple(k.value for k in ConsentKind)
_ACTION_CHOICES = tuple(a.value for a in ConsentAction)
_SOURCE_CHOICES = tuple(s.value for s in ConsentSource)


class ConsentRecordSchema(Schema):
    """Request body for ``POST /me/consents``.

    Records a grant or revocation event of a specific consent kind and
    version. ``source`` is required and intentionally minimal — no IP,
    user-agent or other identifying metadata is captured.
    """

    kind = fields.String(
        required=True,
        validate=validate.OneOf(_KIND_CHOICES),
    )
    version = fields.String(
        required=True,
        validate=validate.Length(min=1, max=32),
    )
    action = fields.String(
        required=True,
        validate=validate.OneOf(_ACTION_CHOICES),
    )
    source = fields.String(
        required=True,
        validate=validate.OneOf(_SOURCE_CHOICES),
    )


class ConsentResponseSchema(Schema):
    """Single consent event serialised for clients."""

    id = fields.UUID(required=True)
    kind = fields.String(required=True)
    version = fields.String(required=True)
    action = fields.String(required=True)
    source = fields.String(required=True)
    created_at = fields.DateTime(required=True)


class ConsentListResponseSchema(Schema):
    """``GET /me/consents`` — latest event per consent kind for the user."""

    items = fields.List(fields.Nested(ConsentResponseSchema), required=True)
    total = fields.Integer(required=True)


class ConsentRevokePathSchema(Schema):
    """Path parameter validation for ``DELETE /me/consents/<kind>``."""

    kind = fields.String(
        required=True,
        validate=validate.OneOf(_KIND_CHOICES),
    )
