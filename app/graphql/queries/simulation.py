from __future__ import annotations

import graphene

from app.application.services.installment_vs_cash_application_service import (
    InstallmentVsCashApplicationError,
    InstallmentVsCashApplicationService,
)
from app.graphql.installment_vs_cash_presenters import (
    raise_installment_vs_cash_graphql_error,
    to_installment_vs_cash_calculation_type,
)
from app.graphql.types import InstallmentVsCashCalculationPayloadType


class SimulationQueryMixin:
    installment_vs_cash_calculate = graphene.Field(
        InstallmentVsCashCalculationPayloadType,
        cash_price=graphene.String(required=True),
        installment_count=graphene.Int(required=True),
        installment_amount=graphene.String(),
        installment_total=graphene.String(),
        first_payment_delay_days=graphene.Int(default_value=30),
        opportunity_rate_type=graphene.String(default_value="manual"),
        opportunity_rate_annual=graphene.String(),
        inflation_rate_annual=graphene.String(required=True),
        fees_enabled=graphene.Boolean(default_value=False),
        fees_upfront=graphene.String(default_value="0.00"),
        scenario_label=graphene.String(),
    )

    def resolve_installment_vs_cash_calculate(
        self,
        _info: graphene.ResolveInfo,
        **kwargs: object,
    ) -> InstallmentVsCashCalculationPayloadType:
        service = InstallmentVsCashApplicationService.with_defaults(None)
        try:
            result = service.calculate(dict(kwargs))
        except InstallmentVsCashApplicationError as exc:
            raise_installment_vs_cash_graphql_error(exc)
        return to_installment_vs_cash_calculation_type(result)
