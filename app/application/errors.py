from __future__ import annotations

from typing import Any


class PublicValidationError(ValueError):
    """Validation error safe to expose to API clients."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.public_message = message
        self.details = details or {}
