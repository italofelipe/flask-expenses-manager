from app.application.errors import PublicValidationError
from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)


def test_map_validation_exception_preserves_public_validation_error() -> None:
    exc = PublicValidationError(
        "Parâmetro 'page' inválido. Informe um inteiro positivo.",
        details={"field": "page"},
    )

    mapped = map_validation_exception(exc, fallback_message="Dados inválidos.")

    assert mapped.message == "Parâmetro 'page' inválido. Informe um inteiro positivo."
    assert mapped.code == "VALIDATION_ERROR"
    assert mapped.status_code == 400
    assert mapped.details == {"field": "page"}


def test_map_validation_exception_masks_generic_value_error() -> None:
    mapped = map_validation_exception(
        ValueError("sqlalchemy engine connection leak"),
        fallback_message="Parâmetros de consulta inválidos.",
    )

    assert mapped.message == "Parâmetros de consulta inválidos."
    assert mapped.code == "VALIDATION_ERROR"
    assert mapped.status_code == 400
    assert mapped.details is None
