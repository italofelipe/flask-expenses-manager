from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from app.extensions.database import db
from app.models.ai_insight import AIInsight, InsightType
from app.models.ai_insight_run import AIInsightRun, AIInsightRunStatus
from app.models.user import User
from app.services.ai_monthly_report_service import (
    create_monthly_report_run,
    process_monthly_report_run,
)
from app.services.email_provider import get_email_outbox
from app.services.llm_provider import LLMResponse


def _create_user() -> uuid.UUID:
    user = User(
        name="Mensal Tester",
        email=f"monthly-{uuid.uuid4().hex[:8]}@email.com",
        password="hash",
    )
    db.session.add(user)
    db.session.commit()
    return user.id


def _register_and_login(client, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    reg = client.post(
        "/auth/register",
        json={
            "name": f"{prefix}-{suffix}",
            "email": email,
            "password": "StrongPass@123",
        },
    )
    assert reg.status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass@123"},
    )
    assert login.status_code == 200
    return login.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _grant_premium(app, token: str) -> uuid.UUID:
    with app.app_context():
        from flask_jwt_extended import decode_token

        from app.models.entitlement import Entitlement, EntitlementSource

        user_id = uuid.UUID(decode_token(token)["sub"])
        db.session.add(
            Entitlement(
                user_id=user_id,
                feature_key="advanced_simulations",
                source=EntitlementSource.MANUAL,
                expires_at=None,
            )
        )
        db.session.commit()
        return user_id


def _insight_content(summary: str, dimension: str = "general") -> str:
    return json.dumps(
        {
            "summary": summary,
            "items": [
                {
                    "type": "saude_financeira",
                    "dimension": dimension,
                    "title": "Resumo",
                    "message": summary,
                    "evidence": ["current_period.paid.balance"],
                }
            ],
        },
        ensure_ascii=False,
    )


def _create_insight(
    user_id: uuid.UUID,
    *,
    insight_type: InsightType,
    period_label: str,
    period_start: date,
    period_end: date,
    summary: str,
) -> AIInsight:
    insight = AIInsight(
        user_id=user_id,
        content=_insight_content(summary),
        insight_type=insight_type,
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        model="gpt-test",
        tokens_used=100,
        cost_usd=Decimal("0.00001"),
    )
    db.session.add(insight)
    db.session.commit()
    return insight


def _monthly_llm_response() -> LLMResponse:
    dimensions = [
        ("general", "Panorama mensal", "monthly_report_context.daily_insights"),
        (
            "transactions",
            "Movimentação mensal",
            "data_quality.domain_presence.transactions",
        ),
        ("goals", "Metas do mês", "data_quality.domain_presence.goals"),
        ("budgets", "Orçamentos do mês", "data_quality.domain_presence.budgets"),
        ("credit_cards", "Cartões do mês", "data_quality.domain_presence.credit_cards"),
        ("wallet", "Carteira do mês", "data_quality.domain_presence.wallet"),
    ]
    return LLMResponse(
        content=json.dumps(
            {
                "summary": "Relatório mensal consolidado.",
                "items": [
                    {
                        "type": "saude_financeira",
                        "dimension": dimension,
                        "title": title,
                        "message": (
                            "O mês foi consolidado com base nos insights diários."
                        ),
                        "evidence": [evidence],
                    }
                    for dimension, title, evidence in dimensions
                ],
            },
            ensure_ascii=False,
        ),
        prompt_tokens=100,
        completion_tokens=80,
        total_tokens=180,
        model="gpt-test",
        latency_ms=50,
    )


class StaticProvider:
    def __init__(self) -> None:
        self.calls = 0

    def generate_with_usage(self, prompt: str, response_schema=None) -> LLMResponse:
        self.calls += 1
        assert "monthly_report_context" in prompt
        assert "Daily 1" in prompt
        assert "Relatório anterior" in prompt
        return _monthly_llm_response()


class TestMonthlyReportService:
    def test_create_run_persists_monthly_context_with_daily_history(self, app) -> None:
        with app.app_context():
            user_id = _create_user()
            previous = _create_insight(
                user_id,
                insight_type=InsightType.monthly,
                period_label="2026-04",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 4, 30),
                summary="Relatório anterior",
            )
            _create_insight(
                user_id,
                insight_type=InsightType.daily,
                period_label="2026-05-01",
                period_start=date(2026, 5, 1),
                period_end=date(2026, 5, 1),
                summary="Daily 1",
            )
            _create_insight(
                user_id,
                insight_type=InsightType.daily,
                period_label="2026-05-02",
                period_start=date(2026, 5, 2),
                period_end=date(2026, 5, 2),
                summary="Daily 2",
            )

            result = create_monthly_report_run(
                user_id=user_id,
                anchor_date=date(2026, 5, 21),
            )

            run = db.session.get(AIInsightRun, uuid.UUID(result["run_id"]))
            assert run is not None
            assert run.status == AIInsightRunStatus.previewed
            assert run.period_type == InsightType.monthly
            assert run.period_label == "2026-05"
            context = run.snapshot_json["monthly_report_context"]
            assert [item["period_label"] for item in context["daily_insights"]] == [
                "2026-05-01",
                "2026-05-02",
            ]
            assert context["previous_monthly_insight"]["period_label"] == (
                previous.period_label
            )
            assert context["previous_monthly_insight"]["summary"] == (
                "Relatório anterior"
            )

    def test_process_run_generates_insight_and_emails_deep_link(self, app) -> None:
        with app.app_context():
            user_id = _create_user()
            _create_insight(
                user_id,
                insight_type=InsightType.daily,
                period_label="2026-05-01",
                period_start=date(2026, 5, 1),
                period_end=date(2026, 5, 1),
                summary="Daily 1",
            )
            _create_insight(
                user_id,
                insight_type=InsightType.monthly,
                period_label="2026-04",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 4, 30),
                summary="Relatório anterior",
            )
            run_result = create_monthly_report_run(
                user_id=user_id,
                anchor_date=date(2026, 5, 21),
            )
            provider = StaticProvider()

            result = process_monthly_report_run(
                run_id=uuid.UUID(run_result["run_id"]),
                llm_provider=provider,
            )

            run = db.session.get(AIInsightRun, uuid.UUID(run_result["run_id"]))
            assert run is not None
            assert run.status == AIInsightRunStatus.generated
            assert run.ai_insight_id is not None
            assert result["status"] == "generated"
            assert result["insight_id"] == str(run.ai_insight_id)
            assert result["deep_link"].endswith(f"/insights?open={run.ai_insight_id}")
            assert provider.calls == 1

            outbox = get_email_outbox()
            assert outbox[-1]["tag"] == "monthly_ai_insight_ready"
            assert str(run.ai_insight_id) in outbox[-1]["html"]
            assert str(run.ai_insight_id) in outbox[-1]["text"]


class TestMonthlyReportEndpoints:
    def test_monthly_report_endpoint_enqueues_traceable_run(self, app, client) -> None:
        token = _register_and_login(client, "monthly-endpoint")
        _grant_premium(app, token)
        run_id = uuid.uuid4()

        with (
            patch(
                "app.controllers.ai.resources.ensure_ai_consent_granted",
                return_value="v1.0",
            ),
            patch(
                "app.controllers.ai.resources.create_monthly_report_run",
                return_value={"run_id": str(run_id), "status": "previewed"},
            ) as create_run,
            patch(
                "app.controllers.ai.resources.enqueue_monthly_report_run",
                return_value={
                    "run_id": str(run_id),
                    "status": "previewed",
                    "queued": True,
                    "job_id": "job-1",
                },
            ) as enqueue_run,
        ):
            resp = client.post(
                "/ai/insights/monthly-report",
                headers=_auth(token),
                json={"anchor_date": "2026-05-21"},
            )

        assert resp.status_code == 202
        payload = resp.get_json()["data"]
        assert payload["run_id"] == str(run_id)
        assert payload["queued"] is True
        create_run.assert_called_once()
        enqueue_run.assert_called_once_with(run_id=run_id)

    def test_insight_detail_endpoint_returns_single_owned_insight(
        self, app, client
    ) -> None:
        token = _register_and_login(client, "monthly-detail")

        with app.app_context():
            from flask_jwt_extended import decode_token

            user_id = uuid.UUID(decode_token(token)["sub"])
            insight = _create_insight(
                user_id,
                insight_type=InsightType.monthly,
                period_label="2026-05",
                period_start=date(2026, 5, 1),
                period_end=date(2026, 5, 31),
                summary="Relatório mensal consolidado",
            )
            insight_id = insight.id

        resp = client.get(f"/ai/insights/{insight_id}", headers=_auth(token))

        assert resp.status_code == 200
        payload = resp.get_json()["data"]
        assert payload["id"] == str(insight_id)
        assert payload["period_type"] == "monthly"
        assert payload["summary"] == "Relatório mensal consolidado"
