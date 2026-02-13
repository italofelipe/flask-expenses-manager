from marshmallow import Schema, fields

from app.docs.schema_name_resolver import resolve_openapi_schema_name


class ExplicitNamedSchema(Schema):
    class Meta:
        name = "ExplicitNamedSchema"

    value = fields.Str()
    amount = fields.Int()


class Transaction(Schema):
    value = fields.Str()


class TransactionSchema(Schema):
    value = fields.Str()
    amount = fields.Int()


def test_resolver_uses_explicit_meta_name() -> None:
    assert resolve_openapi_schema_name(ExplicitNamedSchema) == "ExplicitNamedSchema"


def test_resolver_generates_unique_names_for_similar_classes() -> None:
    first = resolve_openapi_schema_name(Transaction)
    second = resolve_openapi_schema_name(TransactionSchema)

    assert first != second
    assert first.endswith("_Transaction")
    assert second.endswith("_TransactionSchema")


def test_resolver_returns_same_name_for_class_and_instance() -> None:
    expected = resolve_openapi_schema_name(TransactionSchema)
    assert resolve_openapi_schema_name(TransactionSchema()) == expected


def test_resolver_adds_suffix_for_schema_modifiers() -> None:
    base = resolve_openapi_schema_name(ExplicitNamedSchema)
    only_value = resolve_openapi_schema_name(ExplicitNamedSchema(only=("value",)))
    only_amount = resolve_openapi_schema_name(ExplicitNamedSchema(only=("amount",)))

    assert only_value != only_amount
    assert only_value.startswith(f"{base}_")
    assert only_amount.startswith(f"{base}_")
