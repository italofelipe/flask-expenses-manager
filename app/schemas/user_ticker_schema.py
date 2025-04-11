from marshmallow import Schema, fields


class UserTickerSchema(Schema):
    id = fields.UUID(dump_only=True)
    symbol = fields.String(required=True)
    quantity = fields.Float(required=True)
    type = fields.String(required=False)
    user_id = fields.UUID(dump_only=True)  # Changed to required=True
