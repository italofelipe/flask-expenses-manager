from flask_marshmallow import Marshmallow
from marshmallow import Schema, fields, validate

ma = Marshmallow()


class UserRegistrationSchema(Schema):
    name = fields.Str(required=True)
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)


class UserProfileSchema(Schema):
    gender = fields.String(validate=validate.OneOf(["masculino", "feminino", "outro"]))
    birth_date = fields.Date()
    monthly_income = fields.Decimal(as_string=True)
    net_worth = fields.Decimal(as_string=True)
    monthly_expenses = fields.Decimal(as_string=True)
    initial_investment = fields.Decimal(as_string=True)
    monthly_investment = fields.Decimal(as_string=True)
    investment_goal_date = fields.Date()


class UserSchema(Schema):
    id = fields.UUID()
    name = fields.String()
    email = fields.Email()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
