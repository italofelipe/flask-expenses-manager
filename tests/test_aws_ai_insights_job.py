from __future__ import annotations

from scripts import aws_ai_insights_job


def test_build_script_discovers_optional_compose_services_before_starting() -> None:
    script = aws_ai_insights_job._build_script(env_name="prod", mode="weekly")

    service_list_cmd = (
        'docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --services'
    )
    assert service_list_cmd in script
    assert "COMPOSE_SERVICES" in script
    assert "SERVICE_START_ARGS=()" in script
    assert "for SERVICE in db redis; do" in script
    assert "service_is_defined" in script
    assert 'echo "[ai-insights] skipping $SERVICE; not defined in compose"' in script
    assert 'up -d "${SERVICE_START_ARGS[@]}"' in script
    assert "up -d db redis" not in script


def test_build_script_waits_only_for_services_started_by_the_job() -> None:
    script = aws_ai_insights_job._build_script(env_name="prod", mode="weekly")

    assert 'for SERVICE in "${SERVICE_START_ARGS[@]}"; do' in script
    assert "db container was not created" not in script
    assert "redis container was not created" not in script


def test_build_script_still_runs_weekly_command_inside_web_without_deps() -> None:
    script = aws_ai_insights_job._build_script(env_name="prod", mode="weekly")

    assert "run --rm --no-deps \\" in script
    assert "web flask ai weekly-insights" in script


def test_build_script_passes_month_to_monthly_command() -> None:
    script = aws_ai_insights_job._build_script(
        env_name="prod",
        mode="monthly",
        month="2026-05",
    )

    assert "web flask ai monthly-insights --month 2026-05" in script
