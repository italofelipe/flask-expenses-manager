#!/usr/bin/env python3
"""
Auraxis - S1 Patching Baseline via SSM Maintenance Windows.

What this script does
1) Audit: verify our patching Maintenance Windows exist and are configured
   correctly (targets, tasks, parameters).
2) Apply: ensure desired configuration is present (idempotent).
3) Execute: start a Maintenance Window execution on demand and wait for the
   result (so we can validate automation without waiting for the cron schedule).

Design constraints
- No SSH. All actions are performed via AWS APIs/CLI.
- Conservative defaults:
  - DEV: `RebootIfNeeded`
  - PROD: `NoReboot`
  - Install OS updates using `AWS-RunPatchBaseline`
- Outputs are kept readable for human operators (step-by-step).

Prerequisites
- AWS CLI authenticated locally (AWS SSO profile recommended).
- Instances are SSM managed and tagged:
  - App=auraxis
  - Environment=dev|prod
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_PROFILE = "auraxis-admin"
DEFAULT_REGION = "us-east-1"

DEFAULT_DEV_WINDOW_NAME = "auraxis-dev-patching"
DEFAULT_PROD_WINDOW_NAME = "auraxis-prod-patching"

DEFAULT_MW_ROLE_NAME = "auraxis-ssm-maintenance-window-role"

DEFAULT_DEV_SCHEDULE = "cron(0 5 ? * SUN *)"  # 05:00 UTC on Sundays
DEFAULT_PROD_SCHEDULE = "cron(0 6 ? * SUN *)"  # 06:00 UTC on Sundays

PATCH_LOG_GROUP = "/auraxis/ssm/patching"


@dataclass(frozen=True)
class AwsCtx:
    """Immutable context for AWS CLI operations."""

    profile: str
    region: str


class AwsCliError(RuntimeError):
    """Raised when an `aws ...` CLI invocation fails."""


def _run_aws(ctx: AwsCtx, args: list[str], *, expect_json: bool = True) -> Any:
    cmd = ["aws", "--profile", ctx.profile, "--region", ctx.region, *args]
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise AwsCliError(
            (p.stderr or "").strip() or f"AWS CLI failed: {' '.join(cmd)}"
        )
    if not expect_json:
        return p.stdout
    stdout = (p.stdout or "").strip()
    if not stdout:
        return {}
    return json.loads(stdout)


def _get_role_arn(ctx: AwsCtx, role_name: str) -> str:
    out = _run_aws(ctx, ["iam", "get-role", "--role-name", role_name])
    return str(out["Role"]["Arn"])


def _find_window_id(ctx: AwsCtx, name: str) -> str | None:
    out = _run_aws(
        ctx,
        [
            "ssm",
            "describe-maintenance-windows",
            "--filters",
            f"Key=Name,Values={name}",
        ],
    )
    wins = out.get("WindowIdentities") or []
    if not wins:
        return None
    return str(wins[0]["WindowId"])


def _ensure_window(ctx: AwsCtx, *, name: str, schedule: str) -> str:
    wid = _find_window_id(ctx, name)
    if wid:
        return wid
    created = _run_aws(
        ctx,
        [
            "ssm",
            "create-maintenance-window",
            "--name",
            name,
            "--schedule",
            schedule,
            "--duration",
            "2",
            "--cutoff",
            "1",
            "--allow-unassociated-targets",
        ],
    )
    return str(created["WindowId"])


def _ensure_window_enabled(ctx: AwsCtx, window_id: str) -> None:
    _run_aws(
        ctx,
        ["ssm", "update-maintenance-window", "--window-id", window_id, "--enabled"],
        expect_json=False,
    )


def _ensure_target(ctx: AwsCtx, *, window_id: str, name: str, environment: str) -> str:
    out = _run_aws(
        ctx, ["ssm", "describe-maintenance-window-targets", "--window-id", window_id]
    )
    for t in out.get("Targets") or []:
        if t.get("Name") == name:
            return str(t["WindowTargetId"])

    created = _run_aws(
        ctx,
        [
            "ssm",
            "register-target-with-maintenance-window",
            "--window-id",
            window_id,
            "--resource-type",
            "INSTANCE",
            "--name",
            name,
            "--targets",
            "Key=tag:App,Values=auraxis",
            f"Key=tag:Environment,Values={environment}",
        ],
    )
    return str(created["WindowTargetId"])


def _deregister_task_by_name(ctx: AwsCtx, *, window_id: str, name: str) -> None:
    out = _run_aws(
        ctx, ["ssm", "describe-maintenance-window-tasks", "--window-id", window_id]
    )
    for t in out.get("Tasks") or []:
        if t.get("Name") == name:
            _run_aws(
                ctx,
                [
                    "ssm",
                    "deregister-task-from-maintenance-window",
                    "--window-id",
                    window_id,
                    "--window-task-id",
                    str(t["WindowTaskId"]),
                ],
                expect_json=False,
            )
            return


def _deregister_all_patch_tasks(ctx: AwsCtx, *, window_id: str) -> None:
    """
    Remove all existing AWS-RunPatchBaseline tasks from a maintenance window.

    Rationale
    - We want patching to run exactly once per window execution.
    - Historical tasks may exist with older parameter formats (TaskParameters).
    """
    out = _run_aws(
        ctx, ["ssm", "describe-maintenance-window-tasks", "--window-id", window_id]
    )
    for t in out.get("Tasks") or []:
        if t.get("TaskArn") != "AWS-RunPatchBaseline":
            continue
        _run_aws(
            ctx,
            [
                "ssm",
                "deregister-task-from-maintenance-window",
                "--window-id",
                window_id,
                "--window-task-id",
                str(t["WindowTaskId"]),
            ],
            expect_json=False,
        )


def _register_patch_task(
    ctx: AwsCtx,
    *,
    window_id: str,
    window_target_id: str,
    service_role_arn: str,
    name: str,
    reboot_option: str,
) -> str:
    """
    Register a new patching task using AWS-RunPatchBaseline.

    We enable CloudWatch output to a dedicated log group for troubleshooting.
    """
    invocation = {
        "RunCommand": {
            "Parameters": {
                "Operation": ["Install"],
                "RebootOption": [reboot_option],
            },
            "CloudWatchOutputConfig": {
                "CloudWatchOutputEnabled": True,
                "CloudWatchLogGroupName": PATCH_LOG_GROUP,
            },
            "TimeoutSeconds": 7200,
        }
    }

    created = _run_aws(
        ctx,
        [
            "ssm",
            "register-task-with-maintenance-window",
            "--window-id",
            window_id,
            "--name",
            name,
            "--task-arn",
            "AWS-RunPatchBaseline",
            "--task-type",
            "RUN_COMMAND",
            "--targets",
            f"Key=WindowTargetIds,Values={window_target_id}",
            "--service-role-arn",
            service_role_arn,
            "--task-invocation-parameters",
            json.dumps(invocation),
            "--max-concurrency",
            "1",
            "--max-errors",
            "1",
            "--priority",
            "1",
        ],
    )
    return str(created["WindowTaskId"])


def apply(ctx: AwsCtx) -> dict[str, str]:
    """
    Ensure maintenance windows and tasks exist with the desired parameters.
    """
    role_arn = _get_role_arn(ctx, DEFAULT_MW_ROLE_NAME)

    dev_wid = _ensure_window(
        ctx, name=DEFAULT_DEV_WINDOW_NAME, schedule=DEFAULT_DEV_SCHEDULE
    )
    prod_wid = _ensure_window(
        ctx, name=DEFAULT_PROD_WINDOW_NAME, schedule=DEFAULT_PROD_SCHEDULE
    )
    _ensure_window_enabled(ctx, dev_wid)
    _ensure_window_enabled(ctx, prod_wid)

    dev_tgt = _ensure_target(
        ctx, window_id=dev_wid, name="auraxis-dev-patching-target", environment="dev"
    )
    prod_tgt = _ensure_target(
        ctx, window_id=prod_wid, name="auraxis-prod-patching-target", environment="prod"
    )

    # Re-register tasks to guarantee parameter correctness (remove legacy tasks too).
    _deregister_all_patch_tasks(ctx, window_id=dev_wid)
    _deregister_all_patch_tasks(ctx, window_id=prod_wid)

    dev_task_id = _register_patch_task(
        ctx,
        window_id=dev_wid,
        window_target_id=dev_tgt,
        service_role_arn=role_arn,
        name="auraxis-dev-patching-task",
        reboot_option="RebootIfNeeded",
    )
    prod_task_id = _register_patch_task(
        ctx,
        window_id=prod_wid,
        window_target_id=prod_tgt,
        service_role_arn=role_arn,
        name="auraxis-prod-patching-task",
        reboot_option="NoReboot",
    )

    return {
        "dev_window_id": dev_wid,
        "dev_task_id": dev_task_id,
        "prod_window_id": prod_wid,
        "prod_task_id": prod_task_id,
    }


def _check_window_enabled(ctx: AwsCtx, *, name: str, window_id: str) -> list[str]:
    info = _run_aws(ctx, ["ssm", "get-maintenance-window", "--window-id", window_id])
    if info.get("Enabled"):
        return [f"[PASS] window enabled: {name} ({window_id})"]
    return [f"[FAIL] window disabled: {name} ({window_id})"]


def _check_window_targets(ctx: AwsCtx, *, name: str, window_id: str) -> list[str]:
    targets = _run_aws(
        ctx, ["ssm", "describe-maintenance-window-targets", "--window-id", window_id]
    )
    if targets.get("Targets") or []:
        return [f"[PASS] has targets: {name}"]
    return [f"[FAIL] missing targets: {name}"]


def _find_patch_task_reboot_policy(tasks: list[dict[str, Any]]) -> str | None:
    for t in tasks:
        # NOTE: `describe-maintenance-window-tasks` does not always include the
        # invocation parameters. We resolve those via `get-maintenance-window-task`.
        if t.get("TaskArn") != "AWS-RunPatchBaseline":
            continue
        ctx: AwsCtx | None = t.get("__ctx")  # injected by caller for audit
        window_id = t.get("__window_id")
        window_task_id = t.get("WindowTaskId")
        if not ctx or not window_id or not window_task_id:
            continue
        full = _run_aws(
            ctx,
            [
                "ssm",
                "get-maintenance-window-task",
                "--window-id",
                str(window_id),
                "--window-task-id",
                str(window_task_id),
            ],
        )
        inv = (full.get("TaskInvocationParameters") or {}).get("RunCommand") or {}
        params = inv.get("Parameters") or {}
        if isinstance(params.get("RebootOption"), list) and params.get("RebootOption"):
            return str(params["RebootOption"][0])
    return None


def _check_patch_task_policy(
    ctx: AwsCtx, *, name: str, window_id: str, expected_reboot: str
) -> list[str]:
    tasks = _run_aws(
        ctx, ["ssm", "describe-maintenance-window-tasks", "--window-id", window_id]
    )
    task_list = tasks.get("Tasks") or []
    if not task_list:
        return [f"[FAIL] missing tasks: {name}"]

    # Inject context for `_find_patch_task_reboot_policy` to resolve full task details.
    for t in task_list:
        t["__ctx"] = ctx
        t["__window_id"] = window_id
    reboot_policy = _find_patch_task_reboot_policy(task_list)
    if reboot_policy == expected_reboot:
        return [f"[PASS] patch task reboot policy: {expected_reboot}"]
    return [
        (
            "[FAIL] patch task reboot policy mismatch "
            f"(expected {expected_reboot}, got {reboot_policy})"
        )
    ]


def _check_last_execution(ctx: AwsCtx, *, window_id: str) -> list[str]:
    ex = _run_aws(
        ctx,
        [
            "ssm",
            "describe-maintenance-window-executions",
            "--window-id",
            window_id,
            "--max-results",
            "10",
        ],
    )
    execs = ex.get("WindowExecutions") or []
    if not execs:
        return ["[WARN] no maintenance window executions yet (created recently?)"]
    last = execs[0]
    return [
        (
            "[INFO] last execution: "
            f"status={last.get('Status')} start={last.get('StartTime')}"
        )
    ]


def _audit_window(ctx: AwsCtx, *, name: str, expected_reboot: str) -> list[str]:
    wid = _find_window_id(ctx, name)
    if not wid:
        return [f"[FAIL] missing maintenance window: {name}"]

    msgs: list[str] = []
    msgs.extend(_check_window_enabled(ctx, name=name, window_id=wid))
    msgs.extend(_check_window_targets(ctx, name=name, window_id=wid))
    msgs.extend(
        _check_patch_task_policy(
            ctx, name=name, window_id=wid, expected_reboot=expected_reboot
        )
    )
    msgs.extend(_check_last_execution(ctx, window_id=wid))
    return msgs


def audit(ctx: AwsCtx) -> int:
    """
    Audit current patching configuration and print a human-readable report.
    """
    dev_msgs = _audit_window(
        ctx, name=DEFAULT_DEV_WINDOW_NAME, expected_reboot="RebootIfNeeded"
    )
    prod_msgs = _audit_window(
        ctx, name=DEFAULT_PROD_WINDOW_NAME, expected_reboot="NoReboot"
    )
    for m in [*dev_msgs, *prod_msgs]:
        print(m)
    if any(m.startswith("[FAIL]") for m in [*dev_msgs, *prod_msgs]):
        return 2
    return 0


def _wait_for_execution(
    ctx: AwsCtx, *, window_id: str, execution_id: str, timeout_sec: int = 3600
) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        info = _run_aws(
            ctx,
            [
                "ssm",
                "get-maintenance-window-execution",
                "--window-execution-id",
                execution_id,
            ],
        )
        status = str(info.get("Status", ""))
        if status in {"SUCCESS", "FAILED", "TIMED_OUT", "CANCELLED"}:
            return info
        time.sleep(10)
    raise AwsCliError(
        f"Timed out waiting for maintenance window execution: {execution_id}"
    )


def _oneoff_schedule(dt_utc: datetime) -> str:
    """
    Build an AWS cron() expression for a single point in time (UTC).

    We set Year=<current year> to avoid repeating.
    """
    if dt_utc.tzinfo is None:
        raise AwsCliError("dt_utc must be timezone-aware")
    dt_utc = dt_utc.astimezone(timezone.utc)
    return (
        f"cron({dt_utc.minute} {dt_utc.hour} {dt_utc.day} "
        f"{dt_utc.month} ? {dt_utc.year})"
    )


def _create_oneoff_window(ctx: AwsCtx, *, name: str, schedule: str) -> str:
    created = _run_aws(
        ctx,
        [
            "ssm",
            "create-maintenance-window",
            "--name",
            name,
            "--schedule",
            schedule,
            "--duration",
            "2",
            "--cutoff",
            "1",
            "--allow-unassociated-targets",
        ],
    )
    return str(created["WindowId"])


def _delete_window(ctx: AwsCtx, *, window_id: str) -> None:
    _run_aws(
        ctx,
        ["ssm", "delete-maintenance-window", "--window-id", window_id],
        expect_json=False,
    )


def _wait_for_first_execution_id(
    ctx: AwsCtx, *, window_id: str, timeout_sec: int = 900
) -> str:
    """
    Wait until a scheduled window actually starts and produces an execution id.
    """
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        out = _run_aws(
            ctx,
            [
                "ssm",
                "describe-maintenance-window-executions",
                "--window-id",
                window_id,
                "--max-results",
                "10",
            ],
        )
        execs = out.get("WindowExecutions") or []
        if execs:
            return str(execs[0]["WindowExecutionId"])
        time.sleep(10)
    raise AwsCliError(f"Timed out waiting for scheduled window execution: {window_id}")


def validate(ctx: AwsCtx, *, env: str, lead_minutes: int = 4) -> int:
    """
    Validate patching automation by creating a one-off maintenance window.

    This avoids relying on the AWS CLI subcommand `start-maintenance-window-execution`
    which is not available in all builds.
    """
    if env not in {"dev", "prod"}:
        raise AwsCliError("env must be dev or prod")

    role_arn = _get_role_arn(ctx, DEFAULT_MW_ROLE_NAME)
    reboot_option = "RebootIfNeeded" if env == "dev" else "NoReboot"

    now = datetime.now(timezone.utc)
    when = now + timedelta(minutes=lead_minutes)
    schedule = _oneoff_schedule(when)
    name = f"auraxis-{env}-patching-validate-{when.strftime('%Y%m%d%H%M%S')}"

    wid = _create_oneoff_window(ctx, name=name, schedule=schedule)
    try:
        _ensure_window_enabled(ctx, wid)
        tgt = _ensure_target(
            ctx,
            window_id=wid,
            name=f"auraxis-{env}-patching-validate-target",
            environment=env,
        )
        _register_patch_task(
            ctx,
            window_id=wid,
            window_target_id=tgt,
            service_role_arn=role_arn,
            name=f"auraxis-{env}-patching-validate-task",
            reboot_option=reboot_option,
        )

        print(f"one-off window created: {name} ({wid}) schedule={schedule}")
        print("waiting for scheduled execution to appear...")
        execution_id = _wait_for_first_execution_id(ctx, window_id=wid)
        print(f"execution id: {execution_id}")
        final = _wait_for_execution(ctx, window_id=wid, execution_id=execution_id)
        status = str(final.get("Status", ""))
        print(f"final status: {status}")

        tasks = _run_aws(
            ctx,
            [
                "ssm",
                "describe-maintenance-window-execution-tasks",
                "--window-execution-id",
                execution_id,
            ],
        )
        for t in tasks.get("WindowExecutionTaskIdentities") or []:
            print(
                f"- task: {t.get('TaskArn')} "
                f"status={t.get('Status')} id={t.get('TaskExecutionId')}"
            )
        return 0 if status == "SUCCESS" else 3
    finally:
        _delete_window(ctx, window_id=wid)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Auraxis patching baseline (S1)")
    p.add_argument("--profile", default=DEFAULT_PROFILE)
    p.add_argument("--region", default=DEFAULT_REGION)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("audit", help="Audit patching maintenance windows/tasks.")
    sub.add_parser(
        "apply", help="Ensure patching MW config is applied (re-register tasks)."
    )

    p_val = sub.add_parser(
        "validate",
        help="Create a one-off patching window scheduled a few minutes ahead and wait.",
    )
    p_val.add_argument("--env", choices=["dev", "prod"], required=True)
    return p


def main() -> int:
    args = build_parser().parse_args()
    ctx = AwsCtx(profile=args.profile, region=args.region)

    if args.cmd == "audit":
        return audit(ctx)
    if args.cmd == "apply":
        out = apply(ctx)
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    if args.cmd == "validate":
        return validate(ctx, env=str(args.env))

    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
