#!/usr/bin/env python3
"""Canonical CI stack bootstrap for smoke/full release gates."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class BootstrapConfig:
    compose_file: str
    reports_dir: Path
    health_url: str
    migration_command: str
    services: tuple[str, ...]
    up_attempts: int
    migration_attempts: int
    health_attempts: int
    retry_sleep_seconds: int
    health_timeout_seconds: int


@dataclass(frozen=True)
class AttemptRecord:
    phase: str
    attempt: int
    success: bool
    detail: str
    duration_ms: int


@dataclass(frozen=True)
class DiagnosticsArtifacts:
    ps_path: str
    logs_path: str


@dataclass(frozen=True)
class BootstrapReport:
    status: str
    failed_phase: str | None
    total_duration_ms: int
    attempts: list[AttemptRecord] = field(default_factory=list)
    diagnostics: list[DiagnosticsArtifacts] = field(default_factory=list)


class BootstrapError(RuntimeError):
    def __init__(self, phase: str, detail: str) -> None:
        super().__init__(detail)
        self.phase = phase
        self.detail = detail


def _compose_base_args(compose_file: str) -> list[str]:
    return ["docker", "compose", "-f", compose_file]


def _run_subprocess(
    args: list[str], check: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        capture_output=True,
        text=True,
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _dump_state(
    *,
    compose_file: str,
    reports_dir: Path,
    prefix: str,
    services: tuple[str, ...],
) -> DiagnosticsArtifacts:
    reports_dir.mkdir(parents=True, exist_ok=True)
    ps_path = reports_dir / f"{prefix}-ps.txt"
    logs_path = reports_dir / f"{prefix}-logs.txt"

    ps_result = _run_subprocess(_compose_base_args(compose_file) + ["ps"])
    logs_result = _run_subprocess(
        _compose_base_args(compose_file) + ["logs", "--tail=200", *services]
    )

    _write_text(ps_path, ps_result.stdout + ps_result.stderr)
    _write_text(logs_path, logs_result.stdout + logs_result.stderr)

    return DiagnosticsArtifacts(ps_path=str(ps_path), logs_path=str(logs_path))


def _check_health(health_url: str, timeout_seconds: int) -> None:
    request = urllib.request.Request(health_url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        if response.status != 200:
            raise BootstrapError(
                "health",
                f"Health endpoint expected 200, got {response.status}",
            )


def _bootstrap_stack(
    config: BootstrapConfig,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> BootstrapReport:
    started_at = time.perf_counter()
    attempts: list[AttemptRecord] = []
    diagnostics: list[DiagnosticsArtifacts] = []

    for attempt in range(1, config.up_attempts + 1):
        phase_started = time.perf_counter()
        result = _run_subprocess(
            _compose_base_args(config.compose_file) + ["up", "-d", *config.services]
        )
        success = result.returncode == 0
        attempts.append(
            AttemptRecord(
                phase="boot",
                attempt=attempt,
                success=success,
                detail=(result.stderr or result.stdout).strip() or "ok",
                duration_ms=int((time.perf_counter() - phase_started) * 1000),
            )
        )
        if success:
            break
        diagnostics.append(
            _dump_state(
                compose_file=config.compose_file,
                reports_dir=config.reports_dir,
                prefix=f"boot-attempt-{attempt}",
                services=config.services,
            )
        )
        _run_subprocess(
            _compose_base_args(config.compose_file) + ["down", "-v", "--remove-orphans"]
        )
        sleep_fn(attempt * config.retry_sleep_seconds)
    else:
        return BootstrapReport(
            status="failed",
            failed_phase="boot",
            total_duration_ms=int((time.perf_counter() - started_at) * 1000),
            attempts=attempts,
            diagnostics=diagnostics,
        )

    migration_args = shlex.split(config.migration_command)
    for attempt in range(1, config.migration_attempts + 1):
        phase_started = time.perf_counter()
        result = _run_subprocess(
            _compose_base_args(config.compose_file)
            + ["exec", "-T", "web", *migration_args]
        )
        success = result.returncode == 0
        attempts.append(
            AttemptRecord(
                phase="migration",
                attempt=attempt,
                success=success,
                detail=(result.stderr or result.stdout).strip() or "ok",
                duration_ms=int((time.perf_counter() - phase_started) * 1000),
            )
        )
        if success:
            break
        sleep_fn(config.retry_sleep_seconds)
    else:
        diagnostics.append(
            _dump_state(
                compose_file=config.compose_file,
                reports_dir=config.reports_dir,
                prefix="migration-failed",
                services=config.services,
            )
        )
        return BootstrapReport(
            status="failed",
            failed_phase="migration",
            total_duration_ms=int((time.perf_counter() - started_at) * 1000),
            attempts=attempts,
            diagnostics=diagnostics,
        )

    for attempt in range(1, config.health_attempts + 1):
        phase_started = time.perf_counter()
        try:
            _check_health(config.health_url, config.health_timeout_seconds)
            attempts.append(
                AttemptRecord(
                    phase="health",
                    attempt=attempt,
                    success=True,
                    detail="ok",
                    duration_ms=int((time.perf_counter() - phase_started) * 1000),
                )
            )
            break
        except (BootstrapError, urllib.error.URLError) as exc:
            attempts.append(
                AttemptRecord(
                    phase="health",
                    attempt=attempt,
                    success=False,
                    detail=str(exc),
                    duration_ms=int((time.perf_counter() - phase_started) * 1000),
                )
            )
            sleep_fn(config.retry_sleep_seconds)
    else:
        diagnostics.append(
            _dump_state(
                compose_file=config.compose_file,
                reports_dir=config.reports_dir,
                prefix="health-failed",
                services=config.services,
            )
        )
        return BootstrapReport(
            status="failed",
            failed_phase="health",
            total_duration_ms=int((time.perf_counter() - started_at) * 1000),
            attempts=attempts,
            diagnostics=diagnostics,
        )

    return BootstrapReport(
        status="ok",
        failed_phase=None,
        total_duration_ms=int((time.perf_counter() - started_at) * 1000),
        attempts=attempts,
        diagnostics=diagnostics,
    )


def _write_report(path: Path, report: BootstrapReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": report.status,
        "failed_phase": report.failed_phase,
        "total_duration_ms": report.total_duration_ms,
        "attempts": [asdict(record) for record in report.attempts],
        "diagnostics": [asdict(record) for record in report.diagnostics],
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _parse_services(raw: str) -> tuple[str, ...]:
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not parts:
        raise ValueError("services cannot be empty")
    return parts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canonical CI stack bootstrap")
    subparsers = parser.add_subparsers(dest="command", required=True)

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--compose-file", default="docker-compose.ci.yml")
    shared.add_argument("--reports-dir", default="reports/ci-stack")
    shared.add_argument("--services", default="db,redis,web")

    bootstrap = subparsers.add_parser("bootstrap", parents=[shared])
    bootstrap.add_argument("--health-url", default="http://localhost:3333/healthz")
    bootstrap.add_argument("--migration-command", default="flask db upgrade")
    bootstrap.add_argument("--up-attempts", type=int, default=3)
    bootstrap.add_argument("--migration-attempts", type=int, default=20)
    bootstrap.add_argument("--health-attempts", type=int, default=40)
    bootstrap.add_argument("--retry-sleep-seconds", type=int, default=3)
    bootstrap.add_argument("--health-timeout-seconds", type=int, default=3)
    bootstrap.add_argument(
        "--report-path",
        default="reports/ci-stack/bootstrap-report.json",
    )

    dump_state = subparsers.add_parser("dump-state", parents=[shared])
    dump_state.add_argument("--prefix", default="manual")

    subparsers.add_parser("teardown", parents=[shared])
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    compose_file = str(args.compose_file)
    reports_dir = Path(args.reports_dir)
    services = _parse_services(args.services)

    if args.command == "dump-state":
        _dump_state(
            compose_file=compose_file,
            reports_dir=reports_dir,
            prefix=str(args.prefix),
            services=services,
        )
        return 0

    if args.command == "teardown":
        result = _run_subprocess(
            _compose_base_args(compose_file) + ["down", "-v", "--remove-orphans"]
        )
        return result.returncode

    config = BootstrapConfig(
        compose_file=compose_file,
        reports_dir=reports_dir,
        health_url=str(args.health_url),
        migration_command=str(args.migration_command),
        services=services,
        up_attempts=int(args.up_attempts),
        migration_attempts=int(args.migration_attempts),
        health_attempts=int(args.health_attempts),
        retry_sleep_seconds=int(args.retry_sleep_seconds),
        health_timeout_seconds=int(args.health_timeout_seconds),
    )
    report = _bootstrap_stack(config)
    _write_report(Path(args.report_path), report)
    return 0 if report.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
