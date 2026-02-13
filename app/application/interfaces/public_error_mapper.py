from __future__ import annotations

from typing import Protocol

from app.application.dto.public_error_dto import PublicErrorDTO


class PublicErrorMapper(Protocol):
    def from_validation_exception(
        self,
        exc: Exception,
        *,
        fallback_message: str,
    ) -> PublicErrorDTO:
        pass
