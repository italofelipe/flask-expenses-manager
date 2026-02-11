from __future__ import annotations

from typing import Any


def sanitize_text(value: str) -> str:
    stripped = value.strip()
    return "".join(ch for ch in stripped if ch.isprintable() or ch in {"\n", "\t"})


def sanitize_string_fields(data: Any, field_names: set[str]) -> Any:
    if not isinstance(data, dict):
        return data
    sanitized = dict(data)
    for field_name in field_names:
        current = sanitized.get(field_name)
        if isinstance(current, str):
            sanitized[field_name] = sanitize_text(current)
    return sanitized
