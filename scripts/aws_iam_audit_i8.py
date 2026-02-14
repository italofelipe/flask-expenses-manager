#!/usr/bin/env python3
"""
Auraxis - IAM least-privilege audit helper (I8).

What it checks
- For each EC2 instance (DEV/PROD):
  - instance profile attached (if any)
  - role name behind the instance profile
  - attached managed policies
  - inline policies

What it flags (high level)
- Missing instance profile (SSM/CloudWatch/S3 automation will be brittle)
- Suspiciously broad managed policies (e.g., AdministratorAccess)

Why this exists
- I8 requires least-privilege IAM; before changing anything, we audit the
  current role and make changes intentionally.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from typing import Any

DEFAULT_PROFILE = "auraxis-admin"
DEFAULT_REGION = "us-east-1"

DEFAULT_PROD_INSTANCE_ID = "i-0057e3b52162f78f8"
DEFAULT_DEV_INSTANCE_ID = "i-0bb5b392c2188dd3d"


@dataclass(frozen=True)
class AwsCtx:
    profile: str
    region: str


class AwsCliError(RuntimeError):
    pass


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


def _get_instance(ctx: AwsCtx, instance_id: str) -> dict[str, Any]:
    out = _run_aws(
        ctx,
        ["ec2", "describe-instances", "--instance-ids", instance_id],
    )
    reservations = out.get("Reservations") or []
    instances = (reservations[0].get("Instances") or []) if reservations else []
    if not instances:
        raise AwsCliError(f"Instance not found: {instance_id}")
    return dict(instances[0])


def _extract_name(instance: dict[str, Any]) -> str:
    for tag in instance.get("Tags") or []:
        if str(tag.get("Key")) == "Name":
            return str(tag.get("Value") or "")
    return ""


def _role_from_instance_profile_arn(profile_arn: str) -> tuple[str, list[str]]:
    # arn:aws:iam::123456789012:instance-profile/NAME
    name = profile_arn.split("/")[-1]
    return name, [name]


def audit_instance(ctx: AwsCtx, instance_id: str) -> dict[str, Any]:
    inst = _get_instance(ctx, instance_id)
    name = _extract_name(inst)
    resource = f"{instance_id} ({name})" if name else instance_id

    iam_profile = inst.get("IamInstanceProfile") or {}
    arn = str(iam_profile.get("Arn") or "")
    if not arn:
        return {
            "instance": resource,
            "instance_profile": None,
            "role": None,
            "managed_policies": [],
            "inline_policies": [],
            "findings": ["FAIL: instance has no IAM instance profile attached"],
        }

    profile_name, _ = _role_from_instance_profile_arn(arn)
    prof = _run_aws(
        ctx, ["iam", "get-instance-profile", "--instance-profile-name", profile_name]
    )
    roles = prof.get("InstanceProfile", {}).get("Roles", []) or []
    if not roles:
        return {
            "instance": resource,
            "instance_profile": profile_name,
            "role": None,
            "managed_policies": [],
            "inline_policies": [],
            "findings": ["FAIL: instance profile has no roles"],
        }

    role_name = str(roles[0].get("RoleName") or "")

    attached = _run_aws(
        ctx, ["iam", "list-attached-role-policies", "--role-name", role_name]
    )
    managed = [
        str(p.get("PolicyName"))
        for p in (attached.get("AttachedPolicies") or [])
        if p.get("PolicyName")
    ]

    inline = _run_aws(ctx, ["iam", "list-role-policies", "--role-name", role_name])
    inline_names = [str(n) for n in (inline.get("PolicyNames") or [])]

    findings: list[str] = []
    suspicious = {"AdministratorAccess", "PowerUserAccess"}
    for pol in managed:
        if pol in suspicious:
            findings.append(f"FAIL: suspicious broad managed policy attached: {pol}")
        if pol.endswith("FullAccess") and pol not in {
            "AmazonSSMFullAccess",
        }:
            findings.append(f"WARN: managed policy looks broad: {pol}")

    if not managed:
        findings.append(
            "WARN: role has no managed policies attached (verify SSM/Logs work)"
        )

    return {
        "instance": resource,
        "instance_profile": profile_name,
        "role": role_name,
        "managed_policies": sorted(managed),
        "inline_policies": sorted(inline_names),
        "findings": findings
        or ["PASS: no broad managed policies detected (basic heuristic)"],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Auraxis IAM audit helper (I8)")
    p.add_argument("--profile", default=DEFAULT_PROFILE)
    p.add_argument("--region", default=DEFAULT_REGION)
    p.add_argument("--prod-instance-id", default=DEFAULT_PROD_INSTANCE_ID)
    p.add_argument("--dev-instance-id", default=DEFAULT_DEV_INSTANCE_ID)
    return p


def main() -> int:
    args = build_parser().parse_args()
    ctx = AwsCtx(profile=args.profile, region=args.region)
    report = {
        "dev": audit_instance(ctx, str(args.dev_instance_id)),
        "prod": audit_instance(ctx, str(args.prod_instance_id)),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
