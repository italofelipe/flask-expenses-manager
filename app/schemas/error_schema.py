from marshmallow import Schema, fields


class ErrorResponseSchema(Schema):
    message = fields.String(required=True)
    error = fields.String(required=False)
