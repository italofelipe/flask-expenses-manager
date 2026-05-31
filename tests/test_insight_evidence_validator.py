"""Tests for evidence validation pipeline (issue #1300).

Covers:
- per-dimension whitelist enforcement (budgets/goals/credit_cards/transactions)
- general dimension accepts any KNOWN prefix
- unknown prefixes rejected outright
- missing/empty/non-list evidence rejected
- filter_valid_items keeps survivors and logs rejected items
- partial rejection in the full pipeline (coerce → filter)
- all-rejected scenario raises LLMProviderError at service layer
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.services.ai_advisory_service import _coerce_financial_insight_response
from app.services.insight_evidence_validator import (
    filter_valid_items,
    is_known_evidence_prefix,
    validate_item_evidence,
)
from app.services.llm_provider import LLMProviderError

# ──────────────────────────────────────────────────────────────────────────────
# Whitelist of snapshot prefixes
# ──────────────────────────────────────────────────────────────────────────────


class TestKnownPrefixes:
    @pytest.mark.parametrize(
        "path",
        [
            "current_period.paid.balance",
            "transactions.items[0]",
            "credit_cards[1].utilization_pct",
            "wallet.benchmark.cdi_monthly_pct",
            "budgets.envelope.alimentacao",
            "goals.viagem.progress",
            "comparisons.yesterday.delta",
            "daily_series",
            "data_quality.missing_external_rates",
            "financial_health.risk_flags[0].code",
        ],
    )
    def test_accepts_known_prefix(self, path) -> None:
        assert is_known_evidence_prefix(path)

    @pytest.mark.parametrize(
        "path",
        [
            "inventado.coisa",
            "user.email",
            "external.cdi",
            "",
            "   ",
        ],
    )
    def test_rejects_unknown_or_empty(self, path) -> None:
        assert not is_known_evidence_prefix(path)


# ──────────────────────────────────────────────────────────────────────────────
# validate_item_evidence
# ──────────────────────────────────────────────────────────────────────────────


def _item(dimension: str, evidence: list[str], type_: str = "saude_financeira") -> dict:
    return {
        "type": type_,
        "dimension": dimension,
        "title": "x",
        "message": "y",
        "evidence": evidence,
    }


class TestValidateItemEvidence:
    def test_general_accepts_any_known_path(self) -> None:
        ok, reason = validate_item_evidence(
            _item(
                "general",
                ["current_period.paid.balance", "goals.viagem.progress"],
            )
        )
        assert ok is True
        assert reason is None

    def test_budgets_requires_budgets_prefix(self) -> None:
        ok, reason = validate_item_evidence(
            _item("budgets", ["current_period.paid.expense_total"])
        )
        assert ok is False
        assert reason == "dimension_evidence_mismatch"

    def test_budgets_accepts_when_at_least_one_budgets_path(self) -> None:
        ok, reason = validate_item_evidence(
            _item(
                "budgets",
                ["current_period.paid.expense_total", "budgets.alimentacao.used"],
            )
        )
        assert ok is True
        assert reason is None

    def test_goals_dimension_with_goals_evidence_accepted(self) -> None:
        ok, _ = validate_item_evidence(_item("goals", ["goals.viagem.progress"]))
        assert ok

    def test_credit_cards_dimension_requires_credit_cards_path(self) -> None:
        ok, reason = validate_item_evidence(
            _item("credit_cards", ["transactions.items[0]"])
        )
        assert not ok
        assert reason == "dimension_evidence_mismatch"
        ok2, _ = validate_item_evidence(
            _item("credit_cards", ["credit_cards[0].utilization_pct"])
        )
        assert ok2

    def test_transactions_accepts_extremes_and_categories(self) -> None:
        for path in ("extremes.max_expense_day", "categories.top_expense_categories"):
            ok, _ = validate_item_evidence(_item("transactions", [path]))
            assert ok, f"path {path!r} should be accepted for transactions"

    def test_rejects_unknown_dimension(self) -> None:
        ok, reason = validate_item_evidence(_item("investments", ["wallet.items"]))
        assert not ok
        assert reason == "invalid_dimension"

    def test_rejects_missing_evidence(self) -> None:
        ok, reason = validate_item_evidence(_item("general", []))
        assert not ok
        assert reason == "missing_evidence"

    def test_rejects_non_list_evidence(self) -> None:
        item = _item("general", [])
        item["evidence"] = "current_period.paid.balance"
        ok, reason = validate_item_evidence(item)
        assert not ok
        assert reason == "missing_evidence"

    def test_rejects_unknown_prefix_path(self) -> None:
        ok, reason = validate_item_evidence(_item("general", ["inventado.algo"]))
        assert not ok
        assert reason == "unknown_path_prefix"


# ──────────────────────────────────────────────────────────────────────────────
# filter_valid_items
# ──────────────────────────────────────────────────────────────────────────────


class TestFilterValidItems:
    def test_drops_invalid_keeps_valid(self, caplog) -> None:
        items = [
            _item("budgets", ["current_period.paid.expense_total"]),  # invalid
            _item("transactions", ["transactions.items[0]"]),  # valid
            _item("goals", ["goals.x"]),  # valid
        ]
        caplog.set_level("WARNING")
        accepted = filter_valid_items(items, user_id=uuid4())
        assert len(accepted) == 2
        assert any("evidence_validation.rejected" in m for m in caplog.messages)

    def test_empty_input_returns_empty(self) -> None:
        assert filter_valid_items([], user_id=None) == []


# ──────────────────────────────────────────────────────────────────────────────
# Integration with the coercion pipeline
# ──────────────────────────────────────────────────────────────────────────────


def _llm_response(*items: dict, summary: str = "Resumo.") -> str:
    return json.dumps({"summary": summary, "items": list(items)})


class TestPipelineIntegration:
    def test_coerce_keeps_only_valid_items(self) -> None:
        content = _llm_response(
            {
                "type": "saude_financeira",
                "dimension": "budgets",
                "title": "Estouro",
                "message": "...",
                # Misuse: budget claim with only generic evidence
                "evidence": ["current_period.paid.expense_total"],
            },
            {
                "type": "saude_financeira",
                "dimension": "goals",
                "title": "Meta",
                "message": "...",
                "evidence": ["goals.viagem.progress"],
            },
        )
        summary, items, _meta = _coerce_financial_insight_response(content)
        assert summary == "Resumo."
        # Invalid item dropped
        assert len(items) == 1
        assert items[0]["dimension"] == "goals"

    def test_all_rejected_raises_llm_provider_error(self) -> None:
        content = _llm_response(
            {
                "type": "saude_financeira",
                "dimension": "budgets",
                "title": "x",
                "message": "y",
                "evidence": ["current_period.paid.expense_total"],
            }
        )
        with pytest.raises(LLMProviderError):
            _coerce_financial_insight_response(content)


class TestProjectionsEvidence:
    def test_projections_is_known_prefix(self) -> None:
        assert is_known_evidence_prefix("projections.wallet.horizon_12m") is True
        assert is_known_evidence_prefix("projections.goals[0].horizon_3m") is True

    def test_transactions_dimension_accepts_projections_goals_wallet(self) -> None:
        for evidence in (
            "projections.combined_scenario.horizon_12m",
            "goals[0].required_monthly_pace",
            "wallet.total_value",
        ):
            ok, reason = validate_item_evidence(
                {
                    "type": "saude_financeira",
                    "dimension": "transactions",
                    "title": "Narrativa",
                    "message": "...",
                    "evidence": [evidence],
                }
            )
            assert ok is True, (evidence, reason)
