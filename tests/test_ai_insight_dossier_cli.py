"""Tests for AI Insight audit dossier export CLI (#1311)."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path

from click.testing import CliRunner


def _create_dossier_run(app) -> uuid.UUID:
    with app.app_context():
        from app.extensions.database import db
        from app.models.ai_insight import AIInsight, InsightType
        from app.models.ai_insight_run import AIInsightRunStatus
        from app.models.user import User
        from app.services.ai_insight_runs import create_ai_insight_run

        user_id = uuid.uuid4()
        db.session.add(
            User(
                id=user_id,
                name="Dossier User",
                email=f"dossier-{user_id.hex[:8]}@test.com",
                password="x",
            )
        )
        insight = AIInsight(
            user_id=user_id,
            content='{"summary":"Resumo salvo","items":[]}',
            insight_type=InsightType.daily,
            period_label="2026-05-17",
            period_start=date(2026, 5, 17),
            period_end=date(2026, 5, 17),
            model="stub",
            tokens_used=20,
            cost_usd=0,
        )
        db.session.add(insight)
        db.session.flush()
        run = create_ai_insight_run(
            user_id=user_id,
            ai_insight_id=insight.id,
            status=AIInsightRunStatus.generated,
            period_type=InsightType.daily,
            period_label="2026-05-17",
            period_start=date(2026, 5, 17),
            period_end=date(2026, 5, 17),
            snapshot_schema_version="financial_insight_snapshot.v1",
            snapshot_hash="dossier-hash-123",
            prompt_template_version="financial-insight.v1.preview",
            snapshot_json={
                "schema_version": "financial_insight_snapshot.v1",
                "period_type": "daily",
                "period": {
                    "label": "2026-05-17",
                    "start": "2026-05-17",
                    "end": "2026-05-17",
                },
                "current_period": {"paid": {"balance": "100.00"}},
                "comparisons": {},
                "data_quality": {"has_transactions": True},
            },
            evidence_manifest_json={
                "items": [
                    {
                        "path": "current_period.paid.balance",
                        "label": "Saldo pago",
                    }
                ]
            },
            data_quality_json={"has_transactions": True},
        )
        db.session.commit()
        return run.id


def _invoke(app, *args: str):
    from app.cli.ai_insights_cli import ai_insights_cli

    runner = CliRunner()
    with app.app_context():
        return runner.invoke(ai_insights_cli, ["export-dossier", *args])


class TestAIInsightDossierCLI:
    def test_export_dossier_json_by_run_id(self, app, tmp_path: Path) -> None:
        run_id = _create_dossier_run(app)

        result = _invoke(
            app,
            "--run-id",
            str(run_id),
            "--output-dir",
            str(tmp_path),
            "--format",
            "json",
        )

        assert result.exit_code == 0
        output_path = tmp_path / f"ai-insight-dossier-{run_id}.json"
        assert output_path.exists()
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["run"]["id"] == str(run_id)
        assert payload["run"]["snapshot_hash"] == "dossier-hash-123"
        assert payload["snapshot"]["period"]["label"] == "2026-05-17"
        assert payload["evidence_manifest"]["items"][0]["path"] == (
            "current_period.paid.balance"
        )

    def test_export_dossier_html_by_run_id(self, app, tmp_path: Path) -> None:
        run_id = _create_dossier_run(app)

        result = _invoke(
            app,
            "--run-id",
            str(run_id),
            "--output-dir",
            str(tmp_path),
            "--format",
            "html",
        )

        assert result.exit_code == 0
        output_path = tmp_path / f"ai-insight-dossier-{run_id}.html"
        assert output_path.exists()
        html = output_path.read_text(encoding="utf-8")
        assert "dossier-hash-123" in html
        assert "current_period.paid.balance" in html
