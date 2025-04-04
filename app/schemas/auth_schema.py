from marshmallow import Schema, ValidationError, fields, validates_schema


class AuthSchema(Schema):
    email = fields.String(load_default=None)
    name = fields.String(load_default=None)
    password = fields.String(required=True)

    @validates_schema  # type: ignore[misc]
    def validate_identity(self, data: dict[str, str], **kwargs: object) -> None:
        if not data.get("email") and not data.get("name"):
            raise ValidationError("Either 'email' or 'name' must be provided.")


class AuthSuccessResponseSchema(Schema):
    message = fields.String(required=True)
    token = fields.String(required=True)
    user = fields.Dict(required=True, keys=fields.String(), values=fields.String())
