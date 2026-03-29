#!/usr/bin/env python3
"""Low-cost canary runner and economic report for the CI suite."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_WEB_IMAGE = "auraxis-ci-dev:canary"
DEFAULT_RUNNER_COST_PER_MINUTE_USD = 0.008


@dataclass(frozen=True)
class PhaseResult:
    name: str
    success: bool
    duration_ms: int
    command: str
    detail: str


@dataclass(frozen=True)
class CanaryReport:
    status: str
    total_duration_ms: int
    estimated_runner_minutes: float
    estimated_runner_cost_usd: float
    redundant_rebuilds: int
    sustainability_flags: list[str] = field(default_factory=list)
    phases: list[PhaseResult] = field(default_factory=list)


class CanaryError(RuntimeError):
    """Raised when the canary suite cannot pass."""


def _run_command(args: list[str], *, env: dict[str, str] | None = None) -> PhaseResult:
    started_at = time.perf_counter()
    result = subprocess.run(args, capture_output=True, text=True, check=False, env=env)
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    detail = (result.stderr or result.stdout).strip() or "ok"
    return PhaseResult(
        name=" ".join(args[:2]),
        success=result.returncode == 0,
        duration_ms=duration_ms,
        command=" ".join(args),
        detail=detail,
    )


def _run_named_phase(
    *,
    phase_name: str,
    args: list[str],
    env: dict[str, str] | None = None,
) -> PhaseResult:
    result = _run_command(args, env=env)
    return PhaseResult(
        name=phase_name,
        success=result.success,
        duration_ms=result.duration_ms,
        command=result.command,
        detail=result.detail,
    )


def _phase_or_raise(result: PhaseResult) -> PhaseResult:
    if not result.success:
        raise CanaryError(f"{result.name} failed: {result.detail}")
    return result


def _build_flags(
    *,
    total_duration_ms: int,
    bootstrap_duration_ms: int | None,
    smoke_duration_ms: int | None,
    max_total_duration_ms: int,
    max_bootstrap_duration_ms: int,
    max_smoke_duration_ms: int,
) -> list[str]:
    flags: list[str] = []
    if total_duration_ms > max_total_duration_ms:
        flags.append("total_duration_budget_exceeded")
    if (
        bootstrap_duration_ms is not None
        and bootstrap_duration_ms > max_bootstrap_duration_ms
    ):
        flags.append("bootstrap_duration_budget_exceeded")
    if smoke_duration_ms is not None and smoke_duration_ms > max_smoke_duration_ms:
        flags.append("smoke_duration_budget_exceeded")
    return flags


def _render_summary(report: CanaryReport) -> str:
    lines = [
        "## CI suite canary",
        "",
        f"- Status: `{report.status}`",
        f"- Total duration ms: `{report.total_duration_ms}`",
        f"- Estimated runner minutes: `{report.estimated_runner_minutes}`",
        f"- Estimated runner cost usd: `{report.estimated_runner_cost_usd}`",
        f"- Redundant rebuilds: `{report.redundant_rebuilds}`",
        f"- Sustainability flags: `{', '.join(report.sustainability_flags) or 'none'}`",
        "- Phases:",
    ]
    for phase in report.phases:
        status = "pass" if phase.success else "fail"
        lines.append(
            f"  - `{phase.name}` = `{status}` duration_ms=`{phase.duration_ms}`"
        )
    return "\n".join(lines) + "\n"


def _write_report(report: CanaryReport, report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "suite-canary-report.json").write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (report_dir / "suite-canary-report.md").write_text(
        _render_summary(report),
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run low-cost CI suite canary")
    parser.add_argument("--compose-file", default="docker-compose.ci.yml")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--report-dir", default="reports/ci-canary")
    parser.add_argument("--web-image", default=DEFAULT_WEB_IMAGE)
    parser.add_argument("--base-url", default="http://localhost:3333")
    parser.add_argument("--env-name", default="canary")
    parser.add_argument("--latency-samples", type=int, default=2)
    parser.add_argument(
        "--runner-cost-per-minute-usd",
        type=float,
        default=DEFAULT_RUNNER_COST_PER_MINUTE_USD,
    )
    parser.add_argument("--max-total-duration-ms", type=int, default=720000)
    parser.add_argument("--max-bootstrap-duration-ms", type=int, default=240000)
    parser.add_argument("--max-smoke-duration-ms", type=int, default=180000)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    if not Path(args.env_file).exists():
        Path(args.env_file).write_text(
            Path(".env.dev.example").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    env = dict(os.environ)
    env["WEB_IMAGE"] = str(args.web_image)

    started_at = time.perf_counter()
    phases: list[PhaseResult] = []

    try:
        phases.append(
            _phase_or_raise(
                _run_named_phase(
                    phase_name="build_image",
                    args=[
                        "bash",
                        "scripts/ci_image_artifact.sh",
                        "build",
                        "dev",
                        str(args.web_image),
                    ],
                    env=env,
                )
            )
        )
        phases.append(
            _phase_or_raise(
                _run_named_phase(
                    phase_name="suite_doctor",
                    args=[
                        "python3",
                        "scripts/ci_suite_doctor.py",
                        "--compose-file",
                        str(args.compose_file),
                        "--env-file",
                        str(args.env_file),
                        "--web-image",
                        str(args.web_image),
                        "--report-path",
                        str(report_dir / "doctor-report.json"),
                        "--summary-path",
                        str(report_dir / "doctor-summary.md"),
                    ],
                    env=env,
                )
            )
        )
        phases.append(
            _phase_or_raise(
                _run_named_phase(
                    phase_name="stack_bootstrap",
                    args=[
                        "python3",
                        "scripts/ci_stack_bootstrap.py",
                        "bootstrap",
                        "--compose-file",
                        str(args.compose_file),
                        "--reports-dir",
                        str(report_dir / "stack"),
                        "--report-path",
                        str(report_dir / "stack" / "bootstrap-report.json"),
                    ],
                    env=env,
                )
            )
        )
        phases.append(
            _phase_or_raise(
                _run_named_phase(
                    phase_name="http_smoke",
                    args=[
                        "python3",
                        "scripts/http_smoke_check.py",
                        "--base-url",
                        str(args.base_url),
                        "--env-name",
                        str(args.env_name),
                    ],
                    env=env,
                )
            )
        )
        phases.append(
            _phase_or_raise(
                _run_named_phase(
                    phase_name="latency_budget",
                    args=[
                        "python3",
                        "scripts/http_latency_budget_gate.py",
                        "--base-url",
                        str(args.base_url),
                        "--samples",
                        str(args.latency_samples),
                    ],
                    env=env,
                )
            )
        )
        status = "ok"
    except CanaryError as exc:
        phases.append(
            PhaseResult(
                name="failure",
                success=False,
                duration_ms=0,
                command="n/a",
                detail=str(exc),
            )
        )
        status = "failed"
    finally:
        teardown = _run_named_phase(
            phase_name="stack_teardown",
            args=[
                "python3",
                "scripts/ci_stack_bootstrap.py",
                "teardown",
                "--compose-file",
                str(args.compose_file),
            ],
            env=env,
        )
        phases.append(teardown)
        if not teardown.success:
            status = "failed"

    total_duration_ms = int((time.perf_counter() - started_at) * 1000)
    bootstrap_duration_ms = next(
        (phase.duration_ms for phase in phases if phase.name == "stack_bootstrap"),
        None,
    )
    smoke_duration_ms = next(
        (phase.duration_ms for phase in phases if phase.name == "http_smoke"),
        None,
    )
    report = CanaryReport(
        status=status,
        total_duration_ms=total_duration_ms,
        estimated_runner_minutes=round(total_duration_ms / 60000, 2),
        estimated_runner_cost_usd=round(
            (total_duration_ms / 60000) * float(args.runner_cost_per_minute_usd),
            4,
        ),
        redundant_rebuilds=0,
        sustainability_flags=_build_flags(
            total_duration_ms=total_duration_ms,
            bootstrap_duration_ms=bootstrap_duration_ms,
            smoke_duration_ms=smoke_duration_ms,
            max_total_duration_ms=int(args.max_total_duration_ms),
            max_bootstrap_duration_ms=int(args.max_bootstrap_duration_ms),
            max_smoke_duration_ms=int(args.max_smoke_duration_ms),
        ),
        phases=phases,
    )
    _write_report(report, report_dir)
    return 0 if report.status == "ok" and not report.sustainability_flags else 1


if __name__ == "__main__":
    raise SystemExit(main())
