from __future__ import annotations

from typing import NoReturn, cast

from app.application.services.installment_vs_cash_application_service import (
    InstallmentVsCashApplicationError,
)
from app.graphql.errors import build_public_graphql_error, to_public_graphql_code
from app.graphql.types import (
    InstallmentVsCashAssumptionsType,
    InstallmentVsCashCalculationPayloadType,
    InstallmentVsCashCashOptionType,
    InstallmentVsCashComparisonType,
    InstallmentVsCashIndicatorSnapshotType,
    InstallmentVsCashInputType,
    InstallmentVsCashInstallmentOptionType,
    InstallmentVsCashNeutralityBandType,
    InstallmentVsCashOptionsType,
    InstallmentVsCashResultType,
    InstallmentVsCashScheduleItemType,
    InstallmentVsCashSimulationType,
)
from app.services.installment_vs_cash_types import (
    InstallmentVsCashCalculationResponse,
    InstallmentVsCashIndicatorSnapshot,
    InstallmentVsCashNormalizedInput,
    InstallmentVsCashResult,
    InstallmentVsCashScheduleItem,
    SerializedSimulation,
)


def raise_installment_vs_cash_graphql_error(
    exc: InstallmentVsCashApplicationError,
) -> NoReturn:
    raise build_public_graphql_error(
        exc.message,
        code=to_public_graphql_code(exc.code),
    ) from exc


def to_installment_vs_cash_calculation_type(
    payload: InstallmentVsCashCalculationResponse,
) -> InstallmentVsCashCalculationPayloadType:
    return InstallmentVsCashCalculationPayloadType(
        tool_id=payload["tool_id"],
        rule_version=payload["rule_version"],
        input=to_installment_vs_cash_input_type(payload["input"]),
        result=to_installment_vs_cash_result_type(payload["result"]),
    )


def to_installment_vs_cash_simulation_type(
    simulation: SerializedSimulation,
) -> InstallmentVsCashSimulationType:
    return InstallmentVsCashSimulationType(
        id=simulation["id"],
        user_id=simulation["user_id"],
        tool_id=simulation["tool_id"],
        rule_version=simulation["rule_version"],
        input=to_installment_vs_cash_input_type(
            cast(InstallmentVsCashNormalizedInput, simulation["inputs"])
        ),
        result=to_installment_vs_cash_result_type(
            cast(InstallmentVsCashResult, simulation["result"])
        ),
        saved=simulation["saved"],
        goal_id=simulation["goal_id"],
        created_at=simulation["created_at"],
    )


def to_installment_vs_cash_input_type(
    payload: InstallmentVsCashNormalizedInput,
) -> InstallmentVsCashInputType:
    return InstallmentVsCashInputType(**payload)


def to_installment_vs_cash_result_type(
    payload: InstallmentVsCashResult,
) -> InstallmentVsCashResultType:
    return InstallmentVsCashResultType(
        recommended_option=payload["recommended_option"],
        recommendation_reason=payload["recommendation_reason"],
        formula_explainer=payload["formula_explainer"],
        comparison=InstallmentVsCashComparisonType(**payload["comparison"]),
        options=InstallmentVsCashOptionsType(
            cash=InstallmentVsCashCashOptionType(**payload["options"]["cash"]),
            installment=InstallmentVsCashInstallmentOptionType(
                **payload["options"]["installment"]
            ),
        ),
        neutrality_band=InstallmentVsCashNeutralityBandType(
            **payload["neutrality_band"]
        ),
        assumptions=InstallmentVsCashAssumptionsType(**payload["assumptions"]),
        indicator_snapshot=to_installment_vs_cash_indicator_snapshot_type(
            payload["indicator_snapshot"]
        ),
        schedule=[
            InstallmentVsCashScheduleItemType(**item)
            for item in cast(list[InstallmentVsCashScheduleItem], payload["schedule"])
        ],
    )


def to_installment_vs_cash_indicator_snapshot_type(
    payload: InstallmentVsCashIndicatorSnapshot | None,
) -> InstallmentVsCashIndicatorSnapshotType | None:
    if payload is None:
        return None
    return InstallmentVsCashIndicatorSnapshotType(**payload)
