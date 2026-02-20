from __future__ import annotations

from typing import NoReturn

from app.application.services.investment_application_service import (
    InvestmentApplicationError,
)
from app.graphql.errors import build_public_graphql_error, to_public_graphql_code
from app.services.investment_operation_service import InvestmentOperationError


def raise_investment_graphql_error(
    exc: InvestmentApplicationError | InvestmentOperationError,
) -> NoReturn:
    raise build_public_graphql_error(
        exc.message,
        code=to_public_graphql_code(exc.code),
    ) from exc
