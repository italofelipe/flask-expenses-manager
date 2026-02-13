"""Custom schema resolver used by apispec to avoid component-name collisions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from apispec.ext.marshmallow.common import MODIFIERS
from marshmallow import Schema


def _normalize_modifier_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_modifier_value(item) for key, item in value.items()
        }
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return sorted(str(item) for item in value)
    return value


def _modifiers_suffix(schema: type[Schema] | Schema | Any) -> str:
    if not isinstance(schema, Schema):
        return ""

    modifiers_payload: dict[str, Any] = {}
    for modifier in MODIFIERS:
        value = getattr(schema, modifier, None)
        if not value:
            continue
        modifiers_payload[modifier] = _normalize_modifier_value(value)

    if not modifiers_payload:
        return ""

    payload = json.dumps(modifiers_payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
    return f"_{digest}"


def _base_schema_name(schema: type[Schema] | Schema | Any) -> str:
    schema_cls: type[Any] = schema if isinstance(schema, type) else schema.__class__
    meta_name = getattr(getattr(schema_cls, "Meta", object), "name", None)
    if isinstance(meta_name, str):
        cleaned_name = meta_name.strip()
        if cleaned_name:
            return cleaned_name

    safe_module = schema_cls.__module__.replace(".", "_").replace("-", "_")
    return f"{safe_module}_{schema_cls.__name__}"


def resolve_openapi_schema_name(schema: type[Schema] | Schema | Any) -> str:
    """Return deterministic and collision-resistant names for OpenAPI schemas.

    Priority:
    1. Use explicit ``Meta.name`` when provided by the schema.
    2. Fallback to ``<full_module>_<class_name>`` (sanitized).
    3. Add a deterministic suffix when schema modifiers are present
       (``only/exclude/load_only/dump_only/partial``), preventing collisions
       between variants of the same schema class.
    """

    return f"{_base_schema_name(schema)}{_modifiers_suffix(schema)}"
