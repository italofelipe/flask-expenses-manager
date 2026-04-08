"""Domain error types for the transaction application layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TransactionApplicationError(Exception):
    message: str
    code: str
    status_code: int
    details: dict[str, Any] | None = None
