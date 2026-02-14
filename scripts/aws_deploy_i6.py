#!/usr/bin/env python3
"""
Auraxis - Deploy helper (I6) via SSM (no SSH).

Status
- This is a pragmatic stepping stone before full GitHub Actions -> AWS deploy.
- It provides:
  - deploy to DEV/PROD by git ref (branch/tag/commit)
  - basic rollback (deploy previous successfully deployed ref)
  - status (show deployed refs)
  - deterministic execution with SSM + wait-for-success

Why this exists
- We can ship safely without waiting for IAM/OIDC wiring for GitHub Actions.
- We keep infra changes auditable and repeatable.

What it does on the instance
- Locates repo dir in `/opt/auraxis` (preferred) or `/opt/flask_expenses` (legacy).
- Runs `git fetch` and force-checkouts a ref (defaults to `origin/master`).
- Ensures required runtime env keys for hardened prod configs.
- Renders Nginx config:
  - PROD: TLS (requires cert already provisioned)
  - DEV: HTTP (until dev TLS is provisioned)
- Restarts compose with `docker-compose.prod.yml` (+ optional overlays).
 - Tracks deploy state in `/var/lib/auraxis/deploy_state.json` (per-instance).

Operator prerequisites
- AWS CLI auth working locally.
- EC2 instances are SSM-managed.
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

DEPLOY_STATE_PATH = "/var/lib/auraxis/deploy_state.json"


@dataclass(frozen=True)
class AwsCtx:
    profile: str
    region: str


class AwsCliError(RuntimeError):
    pass


def _run_aws(ctx: AwsCtx, args: list[str], *, expect_json: bool = True) -> Any:
    cmd: list[str] = ["aws"]
    # In CI (GitHub Actions OIDC), we prefer env credentials and may not have a profile.
    if ctx.profile:
        cmd.extend(["--profile", ctx.profile])
    if ctx.region:
        cmd.extend(["--region", ctx.region])
    cmd.extend(args)
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


def _ssm_send_shell(ctx: AwsCtx, instance_id: str, script: str, comment: str) -> str:
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    cmd = (
        "TMP=/tmp/auraxis_ssm_deploy_i6_$$.sh; "
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
            instance_id,
            "--document-name",
            "AWS-RunShellScript",
            "--comment",
            comment,
            "--parameters",
            payload,
        ],
    )
    return str(out["Command"]["CommandId"])


def _wait(ctx: AwsCtx, *, command_id: str, instance_id: str) -> None:
    deadline = time.time() + 1200
    while time.time() < deadline:
        out = _run_aws(
            ctx,
            [
                "ssm",
                "get-command-invocation",
                "--command-id",
                command_id,
                "--instance-id",
                instance_id,
                "--plugin-name",
                "aws:RunShellScript",
            ],
        )
        status = str(out.get("Status") or "Unknown")
        if status in {"Pending", "InProgress", "Delayed"}:
            time.sleep(5)
            continue
        if status != "Success":
            stdout = str(out.get("StandardOutputContent") or "").strip()
            stderr = str(out.get("StandardErrorContent") or "").strip()
            raise AwsCliError(
                "Deploy failed. "
                f"instance_id={instance_id} command_id={command_id} status={status}\n"
                f"STDOUT:\n{stdout[-2000:]}\nSTDERR:\n{stderr[-2000:]}"
            )
        return
    raise AwsCliError(
        "Timeout waiting SSM command. "
        f"instance_id={instance_id} command_id={command_id}"
    )


def _build_script(
    *,
    env_name: str,
    aws_region: str,
    git_ref: str | None,
    mode: str,
) -> str:
    domain = "api.auraxis.com.br" if env_name == "prod" else "dev.api.auraxis.com.br"
    cors_origins = (
        "https://www.auraxis.com.br,https://auraxis.com.br,https://app.auraxis.com.br"
        if env_name == "prod"
        else "http://localhost:3000,http://localhost:5173"
    )
    render_nginx = (
        f"""python3 - <<'PY'
from pathlib import Path
root = Path("deploy/nginx")
src = root / "default.tls.conf"
dst = root / "default.conf"
text = src.read_text(encoding="utf-8").replace("__DOMAIN__", "{domain}")
dst.write_text(text, encoding="utf-8")
print("[i6] rendered nginx tls config:", dst)
PY"""
        if env_name == "prod"
        else f"""cat > deploy/nginx/default.conf <<'CONF'
server {{
    listen 80;
    server_name {domain};

    client_max_body_size 10m;
    location /.well-known/acme-challenge/ {{ root /var/www/certbot; }}

    location / {{
        proxy_pass http://web:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
    }}
}}
CONF
echo "[i6] rendered nginx http config: deploy/nginx/default.conf" """
    )

    git_ref_setup = f'GIT_REF="{git_ref}"' if git_ref is not None else 'GIT_REF=""'

    return f"""\
set -euo pipefail

MODE="{mode}"
{git_ref_setup}

REPO=""
if [ -d /opt/auraxis ]; then
  REPO=/opt/auraxis
elif [ -d /opt/flask_expenses ]; then
  REPO=/opt/flask_expenses
else
  echo "Repo not found in /opt."
  exit 2
fi
cd "$REPO"
echo "[i6] repo=$REPO"

STATE_PATH="{DEPLOY_STATE_PATH}"
sudo mkdir -p "$(dirname "$STATE_PATH")"

OP_USER="ubuntu"
if [ ! -d "/home/$OP_USER" ]; then
  OP_USER="$(id -un)"
fi
sudo -u "$OP_USER" git config --global --add safe.directory "$REPO" || true

CURRENT_REF="$(
  sudo -u "$OP_USER" bash -lc "cd '$REPO' && git rev-parse HEAD" || true
)"
CURRENT_BRANCH="$(
  sudo -u "$OP_USER" bash -lc "cd '$REPO' && git rev-parse --abbrev-ref HEAD" || true
)"

STATE_CURRENT=""
STATE_PREVIOUS=""
if [ -f "$STATE_PATH" ]; then
  STATE_CURRENT="$(python3 - <<'PY' "$STATE_PATH"
import json,sys
p=sys.argv[1]
try:
  data=json.load(open(p,'r',encoding='utf-8'))
  print(data.get('current','') or '')
except Exception:
  print('')
PY
)"
  STATE_PREVIOUS="$(python3 - <<'PY' "$STATE_PATH"
import json,sys
p=sys.argv[1]
try:
  data=json.load(open(p,'r',encoding='utf-8'))
  print(data.get('previous','') or '')
except Exception:
  print('')
PY
)"
fi

if [ "$MODE" = "status" ]; then
  echo "[i6] git: branch=$CURRENT_BRANCH head=$CURRENT_REF"
  echo "[i6] state: current=$STATE_CURRENT previous=$STATE_PREVIOUS path=$STATE_PATH"
  exit 0
fi

if [ "$MODE" = "rollback" ]; then
  if [ -z "$STATE_PREVIOUS" ]; then
    echo "[i6] rollback requested but no previous deploy recorded in $STATE_PATH"
    exit 12
  fi
  GIT_REF="$STATE_PREVIOUS"
fi

if [ -z "$GIT_REF" ]; then
  echo "[i6] missing git ref."
  echo "[i6] Provide --git-ref for deploy or ensure state has previous for rollback."
  exit 13
fi

echo "[i6] mode=$MODE git_ref=$GIT_REF"
sudo -u "$OP_USER" bash -lc \\
  "cd '$REPO' && git fetch --all --prune && git checkout -f '$GIT_REF' \\
    && git reset --hard '$GIT_REF'"

NEW_REF="$(sudo -u "$OP_USER" bash -lc "cd '$REPO' && git rev-parse HEAD")"
echo "[i6] new_head=$NEW_REF"

{render_nginx}

ENV_FILE=.env.prod
if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE."
  exit 3
fi

python3 - "$ENV_FILE" "AURAXIS_ENV" "{env_name}" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]); k=sys.argv[2]; v=sys.argv[3]
lines=p.read_text(encoding="utf-8").splitlines()
out=[]; r=False
for line in lines:
    if line.startswith(k+'=') and not r:
        out.append(k+'='+v); r=True
    else:
        out.append(line)
if not r:
    if out and out[-1].strip(): out.append('')
    out.append(k+'='+v)
p.write_text('\\n'.join(out)+'\\n', encoding="utf-8")
PY

python3 - "$ENV_FILE" "AWS_REGION" "{aws_region}" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]); k=sys.argv[2]; v=sys.argv[3]
lines=p.read_text(encoding="utf-8").splitlines()
out=[]; r=False
for line in lines:
    if line.startswith(k+'=') and not r:
        out.append(k+'='+v); r=True
    else:
        out.append(line)
if not r:
    if out and out[-1].strip(): out.append('')
    out.append(k+'='+v)
p.write_text('\\n'.join(out)+'\\n', encoding="utf-8")
PY

python3 - "$ENV_FILE" "CORS_ALLOWED_ORIGINS" "{cors_origins}" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]); k=sys.argv[2]; v=sys.argv[3]
lines=p.read_text(encoding="utf-8").splitlines()
out=[]; r=False
for line in lines:
    if line.startswith(k+'=') and not r:
        out.append(k+'='+v); r=True
    else:
        out.append(line)
if not r:
    if out and out[-1].strip(): out.append('')
    out.append(k+'='+v)
p.write_text('\\n'.join(out)+'\\n', encoding="utf-8")
PY

echo "[i6] restarting compose..."
docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml \\
  up -d --build --force-recreate

echo "[i6] validating healthz..."
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1/healthz >/dev/null; then
    echo "[i6] OK"
    python3 - <<'PY' "$STATE_PATH" "$CURRENT_REF" "$NEW_REF"
import json,sys
path=sys.argv[1]
prev=sys.argv[2] or ""
cur=sys.argv[3] or ""
data={{"previous": prev, "current": cur}}
with open(path,"w",encoding="utf-8") as f:
  json.dump(data,f,indent=2,sort_keys=True)
print("[i6] wrote deploy state:", path, data)
PY
    exit 0
  fi
  sleep 2
done
echo "[i6] healthz validation failed"
exit 5
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Auraxis deploy helper (I6) via SSM")
    p.add_argument("--profile", default=DEFAULT_PROFILE)
    p.add_argument("--region", default=DEFAULT_REGION)
    p.add_argument("--prod-instance-id", default=DEFAULT_PROD_INSTANCE_ID)
    p.add_argument("--dev-instance-id", default=DEFAULT_DEV_INSTANCE_ID)

    sub = p.add_subparsers(dest="cmd", required=True)
    p_deploy = sub.add_parser("deploy", help="Deploy a git ref to DEV/PROD.")
    p_deploy.add_argument("--env", choices=["dev", "prod"], required=True)
    p_deploy.add_argument("--git-ref", default="origin/master")
    p_rb = sub.add_parser(
        "rollback",
        help="Rollback DEV/PROD to the previous successfully deployed ref.",
    )
    p_rb.add_argument("--env", choices=["dev", "prod"], required=True)
    p_status = sub.add_parser("status", help="Show deploy state and current git ref.")
    p_status.add_argument("--env", choices=["dev", "prod"], required=True)
    return p


def main() -> int:
    args = build_parser().parse_args()
    ctx = AwsCtx(profile=args.profile, region=args.region)

    if args.cmd in {"deploy", "rollback", "status"}:
        env_name = str(args.env)
        instance_id = (
            args.dev_instance_id if env_name == "dev" else args.prod_instance_id
        )

        mode = str(args.cmd)
        git_ref: str | None = None
        comment_ref = ""
        if mode == "deploy":
            git_ref = str(args.git_ref)
            comment_ref = f" ref={git_ref}"

        script = _build_script(
            env_name=env_name,
            aws_region=ctx.region,
            git_ref=git_ref,
            mode=mode,
        )
        cmd_id = _ssm_send_shell(
            ctx,
            instance_id,
            script,
            f"auraxis: i6 {mode} ({env_name}){comment_ref}",
        )
        print(f"{env_name.upper()} command_id={cmd_id}")
        _wait(ctx, command_id=cmd_id, instance_id=instance_id)
        return 0

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
