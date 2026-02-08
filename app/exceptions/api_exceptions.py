from typing import Any, Dict, Optional


class APIError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "BAD_REQUEST",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationAPIError(APIError):
    def __init__(
        self,
        message: str = "Erro de validação",
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class UnauthorizedAPIError(APIError):
    def __init__(
        self,
        message: str = "Não autorizado",
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code="UNAUTHORIZED",
            status_code=401,
            details=details,
        )


class ForbiddenAPIError(APIError):
    def __init__(
        self,
        message: str = "Acesso negado",
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code="FORBIDDEN",
            status_code=403,
            details=details,
        )


class NotFoundAPIError(APIError):
    def __init__(
        self,
        message: str = "Recurso não encontrado",
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code="NOT_FOUND",
            status_code=404,
            details=details,
        )
