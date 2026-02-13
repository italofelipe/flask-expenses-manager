from __future__ import annotations

from app.application.dto.public_error_dto import PublicErrorDTO
from app.application.errors import PublicValidationError
from app.application.interfaces.public_error_mapper import PublicErrorMapper


class DefaultPublicErrorMapper(PublicErrorMapper):
    def from_validation_exception(
        self,
        exc: Exception,
        *,
        fallback_message: str,
    ) -> PublicErrorDTO:
        if isinstance(exc, PublicValidationError):
            return PublicErrorDTO(
                message=exc.public_message,
                code="VALIDATION_ERROR",
                status_code=400,
                details=exc.details or None,
            )

        return PublicErrorDTO(
            message=fallback_message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=None,
        )


_DEFAULT_PUBLIC_ERROR_MAPPER = DefaultPublicErrorMapper()


def get_public_error_mapper() -> PublicErrorMapper:
    return _DEFAULT_PUBLIC_ERROR_MAPPER


def map_validation_exception(
    exc: Exception,
    *,
    fallback_message: str,
) -> PublicErrorDTO:
    mapper = get_public_error_mapper()
    return mapper.from_validation_exception(exc, fallback_message=fallback_message)
