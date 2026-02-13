#!/usr/bin/env python3
"""
Auraxis - Apply CloudWatch logging overlay on EC2 (I7) via SSM.

Goal
- Roll out `docker-compose.aws.logging.yml` to DEV/PROD instances without SSH.

What it does (per instance)
1) Locate repo directory (prefers /opt/auraxis, fallback /opt/flask_expenses).
2) `git pull` to fetch latest compose + app changes (including `/healthz`).
3) Ensure `.env.prod` includes:
   - AURAXIS_ENV=dev|prod
   - AWS_REGION=us-east-1 (or provided)
4) Restart stack with the logging overlay:
   docker compose --env-file .env.prod -f docker-compose.prod.yml \\
     -f docker-compose.aws.logging.yml up -d --build --force-recreate
5) Validate liveness locally via Nginx:
   curl http://127.0.0.1/healthz

Safety
- Requires SSM-managed instances.
- Uses idempotent edits to `.env.prod` (only two keys, non-secret).
- Causes brief downtime during container recreation.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any

DEFAULT_PROFILE = "auraxis-admin"
DEFAULT_REGION = "us-east-1"

DEFAULT_PROD_INSTANCE_ID = "i-0057e3b52162f78f8"
DEFAULT_DEV_INSTANCE_ID = "i-0bb5b392c2188dd3d"


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


def _ssm_send_shell(
    ctx: AwsCtx, instance_ids: list[str], script: str, comment: str
) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = (
        "TMP=/tmp/auraxis_ssm_apply_i7_$$.sh; "
        f"echo '{b64}' | base64 -d > \"$TMP\"; "
        'bash "$TMP"; RC=$?; rm -f "$TMP"; exit $RC'
    )
    payload = json.dumps({"commands": [cmd]})
    out = _run_aws(
        ctx,
        [
            "ssm",
            "send-command",
            "--instance-ids",
            *instance_ids,
            "--document-name",
            "AWS-RunShellScript",
            "--comment",
            comment,
            "--parameters",
            payload,
        ],
        expect_json=True,
    )
    return str(out["Command"]["CommandId"])


def _wait_for_command(
    ctx: AwsCtx,
    *,
    command_id: str,
    instance_id: str,
    timeout_seconds: int = 900,
    poll_seconds: int = 5,
) -> None:
    """
    Block until the SSM command finishes (success or failure).

    We keep this small and deterministic; operators can always inspect detailed
    logs in the AWS console if needed.
    """
    deadline = time.time() + timeout_seconds
    last_status = "Unknown"
    while time.time() < deadline:
        out = _run_aws(
            ctx,
            [
                "ssm",
                "list-command-invocations",
                "--command-id",
                command_id,
                "--details",
            ],
        )
        inv = out.get("CommandInvocations") or []
        match = next((i for i in inv if i.get("InstanceId") == instance_id), None)
        if not match:
            time.sleep(poll_seconds)
            continue
        status = str(match.get("Status") or "Unknown")
        last_status = status
        if status in {"Pending", "InProgress", "Delayed"}:
            time.sleep(poll_seconds)
            continue
        if status != "Success":
            plugins = match.get("CommandPlugins") or []
            output = ""
            if plugins:
                output = str(plugins[0].get("Output") or "").strip()
            raise AwsCliError(
                "SSM command failed. "
                f"instance_id={instance_id} command_id={command_id} "
                f"status={status} output={output[:1200]}"
            )
        return
    raise AwsCliError(
        f"Timeout waiting for SSM command. instance_id={instance_id} "
        f"command_id={command_id} last_status={last_status}"
    )


def build_apply_script(*, env_name: str, aws_region: str) -> str:
    return f"""\
set -euo pipefail

REPO=""
if [ -d /opt/auraxis ]; then
  REPO=/opt/auraxis
elif [ -d /opt/flask_expenses ]; then
  REPO=/opt/flask_expenses
else
  echo "Repo not found in /opt. Expected /opt/auraxis or /opt/flask_expenses."
  exit 2
fi

cd "$REPO"

echo "[i7] repo=$REPO"

# Pull latest changes (compose overlay + /healthz).
# We execute git as the non-root operator user to avoid:
# - "dubious ownership" protections
# - missing SSH keys when the repo remote uses `git@github.com:...`
OP_USER="ubuntu"
if [ ! -d "/home/$OP_USER" ]; then
  OP_USER="$(id -un)"
fi

sudo -u "$OP_USER" git config --global --add safe.directory "$REPO" || true
sudo -u "$OP_USER" bash -lc \\
  "cd '$REPO' && git fetch --all --prune && git pull --ff-only"

if [ ! -f docker-compose.aws.logging.yml ]; then
  echo "Missing docker-compose.aws.logging.yml in $REPO after git pull."
  echo "This usually means the repo is not yet on a commit/branch"
  echo "that includes the overlay."
  echo "Merge the branch that adds the overlay, then re-run this script."
  exit 4
fi

ENV_FILE=.env.prod
if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE in $REPO. Create it before applying."
  exit 3
fi

ensure_kv() {{
  local key="$1"
  local value="$2"
  if grep -qE "^${{key}}=" "$ENV_FILE"; then
    sed -i "s/^${{key}}=.*/${{key}}=${{value}}/" "$ENV_FILE"
  else
    printf "\\n%s=%s\\n" "$key" "$value" >> "$ENV_FILE"
  fi
}}

ensure_kv "AURAXIS_ENV" "{env_name}"
ensure_kv "AWS_REGION" "{aws_region}"

echo "[i7] restarting compose with awslogs overlay..."
docker compose --env-file "$ENV_FILE" \\
  -f docker-compose.prod.yml \\
  -f docker-compose.aws.logging.yml \\
  up -d --build --force-recreate

echo "[i7] validating healthz via nginx..."
curl -fsS http://127.0.0.1/healthz >/dev/null
echo "[i7] OK"
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Auraxis apply logging overlay (I7) via SSM"
    )
    p.add_argument("--profile", default=DEFAULT_PROFILE)
    p.add_argument("--region", default=DEFAULT_REGION)
    p.add_argument("--prod-instance-id", default=DEFAULT_PROD_INSTANCE_ID)
    p.add_argument("--dev-instance-id", default=DEFAULT_DEV_INSTANCE_ID)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_apply = sub.add_parser("apply", help="Apply logging overlay to DEV/PROD.")
    p_apply.add_argument("--targets", choices=["dev", "prod", "all"], default="all")
    p_apply.add_argument("--no-wait", action="store_true")
    return p


def main() -> int:
    args = build_parser().parse_args()
    ctx = AwsCtx(profile=args.profile, region=args.region)

    if args.cmd == "apply":
        if args.targets in {"dev", "all"}:
            script = build_apply_script(env_name="dev", aws_region=ctx.region)
            cmd_id = _ssm_send_shell(
                ctx,
                [args.dev_instance_id],
                script,
                "auraxis: i7 apply logging overlay (dev)",
            )
            print(f"DEV command_id={cmd_id}")
            if not args.no_wait:
                _wait_for_command(
                    ctx,
                    command_id=cmd_id,
                    instance_id=args.dev_instance_id,
                )
        if args.targets in {"prod", "all"}:
            script = build_apply_script(env_name="prod", aws_region=ctx.region)
            cmd_id = _ssm_send_shell(
                ctx,
                [args.prod_instance_id],
                script,
                "auraxis: i7 apply logging overlay (prod)",
            )
            print(f"PROD command_id={cmd_id}")
            if not args.no_wait:
                _wait_for_command(
                    ctx,
                    command_id=cmd_id,
                    instance_id=args.prod_instance_id,
                )
        return 0

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
