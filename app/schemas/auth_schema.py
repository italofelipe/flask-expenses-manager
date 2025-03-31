from marshmallow import Schema, fields, validates_schema, ValidationError

class AuthSchema(Schema):
    email = fields.String(load_default=None)
    name = fields.String(load_default=None)
    password = fields.String(required=True)

    @validates_schema
    def validate_identity(self, data, **kwargs):
        if not data.get("email") and not data.get("name"):
            raise ValidationError("Either 'email' or 'name' must be provided.")


class AuthSuccessResponseSchema(Schema):
    message = fields.String(required=True)
    token = fields.String(required=True)
    user = fields.Dict(
        required=True,
        keys=fields.String(),
        values=fields.String()
    )