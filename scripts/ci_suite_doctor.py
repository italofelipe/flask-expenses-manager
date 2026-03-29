#!/usr/bin/env python3
"""Doctor for CI-like local suite prerequisites and operational drift."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    success: bool
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    status: str
    checks: list[DoctorCheck]
    compose_file: str
    env_file: str
    web_image: str


class DoctorError(RuntimeError):
    """Raised when the suite doctor detects blocking drift."""


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _check_command(name: str) -> DoctorCheck:
    resolved = shutil.which(name)
    if resolved is None:
        return DoctorCheck(name=f"command:{name}", success=False, detail="not found")
    return DoctorCheck(
        name=f"command:{name}",
        success=True,
        detail=resolved,
    )


def _check_docker_compose() -> DoctorCheck:
    result = _run(["docker", "compose", "version"])
    if result.returncode != 0:
        detail = (
            result.stderr or result.stdout
        ).strip() or "docker compose unavailable"
        return DoctorCheck(name="docker:compose", success=False, detail=detail)
    return DoctorCheck(
        name="docker:compose",
        success=True,
        detail=(result.stdout or result.stderr).strip(),
    )


def _check_file(name: str, path: Path) -> DoctorCheck:
    if not path.exists():
        return DoctorCheck(name=name, success=False, detail=f"missing: {path}")
    return DoctorCheck(name=name, success=True, detail=str(path))


def _check_image_local(image_ref: str) -> DoctorCheck:
    result = _run(["docker", "image", "inspect", image_ref])
    if result.returncode != 0:
        return DoctorCheck(
            name="docker:image",
            success=False,
            detail=f"image not present locally: {image_ref}",
        )
    return DoctorCheck(
        name="docker:image",
        success=True,
        detail=image_ref,
    )


def _build_report(
    *,
    compose_file: Path,
    env_file: Path,
    web_image: str,
) -> DoctorReport:
    checks = [
        _check_command("docker"),
        _check_command("python3"),
        _check_command("npm"),
        _check_file("compose:file", compose_file),
        _check_file("env:file", env_file),
    ]

    docker_ok = all(
        check.success for check in checks if check.name.startswith("command:docker")
    )
    if docker_ok:
        checks.append(_check_docker_compose())
        checks.append(_check_image_local(web_image))

    status = "ok" if all(check.success for check in checks) else "failed"
    return DoctorReport(
        status=status,
        checks=checks,
        compose_file=str(compose_file),
        env_file=str(env_file),
        web_image=web_image,
    )


def _write_report(report: DoctorReport, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _render_summary(report: DoctorReport) -> str:
    lines = [
        "## CI suite doctor",
        "",
        f"- Status: `{report.status}`",
        f"- Compose file: `{report.compose_file}`",
        f"- Env file: `{report.env_file}`",
        f"- Web image: `{report.web_image}`",
        "- Checks:",
    ]
    for check in report.checks:
        status = "pass" if check.success else "fail"
        lines.append(f"  - `{check.name}` = `{status}` ({check.detail})")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Doctor for CI-like local suite")
    parser.add_argument("--compose-file", default="docker-compose.ci.yml")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--web-image", required=True)
    parser.add_argument("--report-path", default="reports/ci-doctor/report.json")
    parser.add_argument("--summary-path", default="reports/ci-doctor/summary.md")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    report = _build_report(
        compose_file=Path(args.compose_file),
        env_file=Path(args.env_file),
        web_image=str(args.web_image),
    )
    report_path = Path(args.report_path)
    summary_path = Path(args.summary_path)
    _write_report(report, report_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(_render_summary(report), encoding="utf-8")
    if report.status != "ok":
        raise DoctorError("CI suite doctor detected blocking drift.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
