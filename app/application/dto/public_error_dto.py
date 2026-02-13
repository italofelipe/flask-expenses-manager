from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PublicErrorDTO:
    message: str
    code: str = "VALIDATION_ERROR"
    status_code: int = 400
    details: dict[str, Any] | None = None
