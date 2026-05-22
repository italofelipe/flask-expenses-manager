"""RQ job definitions for AI insight background work."""

from __future__ import annotations

from uuid import UUID

from flask import has_app_context


def generate_monthly_report(run_id: str) -> dict[str, object]:
    """Generate a monthly AI insight report for an existing run."""

    def _process() -> dict[str, object]:
        from app.services.ai_monthly_report_service import process_monthly_report_run

        return process_monthly_report_run(run_id=UUID(str(run_id)))

    if has_app_context():
        return _process()

    from app import create_app

    app = create_app()
    with app.app_context():
        return _process()


__all__ = ["generate_monthly_report"]
