#!/usr/bin/env python3
"""
Fix: add ssm:SendCommand permission to auraxis-github-deploy-dev-ssm-role.

Root cause
----------
GitHub Actions deploy to DEV fails with AccessDeniedException:
  "User: .../assumed-role/auraxis-github-deploy-dev-ssm-role/GitHubActions
   is not authorized to perform: ssm:SendCommand on resource:
   arn:aws:ec2:us-east-1:765480282720:instance/i-0bddcfc8ea56c2ba3"

The OIDC role exists and is assumed correctly, but its inline policy is
missing ssm:SendCommand (and companion read actions). This script patches
the role in-place without requiring Terraform or console access.

Usage
-----
  python scripts/aws_fix_dev_deploy_role.py --dry-run   # preview only
  python scripts/aws_fix_dev_deploy_role.py             # apply fix

Prerequisites
-------------
  aws configure --profile auraxis-admin  (or set AWS_PROFILE env var)
  Caller must have iam:PutRolePolicy and iam:GetRolePolicy permissions.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

ROLE_NAME = "auraxis-github-deploy-dev-ssm-role"
POLICY_NAME = "AuraxisDevDeploySsmPolicy"
DEV_INSTANCE_ID = "i-0bddcfc8ea56c2ba3"
REGION = "us-east-1"
ACCOUNT_ID = "765480282720"


def _run(cmd: list[str], *, dry_run: bool = False) -> str:
    if dry_run:
        print(f"[dry-run] would run: {' '.join(cmd)}")
        return ""
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"[ERROR] {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def get_existing_policy(profile: str) -> dict | None:
    cmd = [
        "aws",
        "iam",
        "get-role-policy",
        "--role-name",
        ROLE_NAME,
        "--policy-name",
        POLICY_NAME,
        "--output",
        "json",
    ]
    if profile:
        cmd = ["aws", "--profile", profile] + cmd[1:]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        if "NoSuchEntity" in result.stderr:
            return None
        print(f"[WARN] get-role-policy: {result.stderr.strip()}")
        return None
    data = json.loads(result.stdout)
    raw = data.get("PolicyDocument", "{}")
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def build_policy() -> dict:
    """Return the minimal SSM deploy policy for the dev role."""
    instance_arn = f"arn:aws:ec2:{REGION}:{ACCOUNT_ID}:instance/{DEV_INSTANCE_ID}"
    ssm_wildcard = f"arn:aws:ssm:{REGION}:{ACCOUNT_ID}:*"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "SSMSendCommandDev",
                "Effect": "Allow",
                "Action": ["ssm:SendCommand"],
                "Resource": [
                    instance_arn,
                    f"arn:aws:ssm:{REGION}::document/AWS-RunShellScript",
                ],
            },
            {
                "Sid": "SSMReadDev",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetCommandInvocation",
                    "ssm:ListCommandInvocations",
                    "ssm:DescribeInstanceInformation",
                ],
                "Resource": [ssm_wildcard],
            },
            {
                "Sid": "EC2DescribeDev",
                "Effect": "Allow",
                "Action": ["ec2:DescribeInstances"],
                "Resource": "*",
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="auraxis-admin")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dry_run: bool = args.dry_run
    profile: str = args.profile

    print(f"Role:   {ROLE_NAME}")
    print(f"Policy: {POLICY_NAME}")
    print(f"Mode:   {'dry-run' if dry_run else 'APPLY'}")
    print()

    existing = get_existing_policy(profile)
    if existing:
        print(f"[INFO] existing policy found:\n{json.dumps(existing, indent=2)}")
    else:
        print("[INFO] no existing inline policy found — will create.")

    new_policy = build_policy()
    print(f"\n[INFO] target policy:\n{json.dumps(new_policy, indent=2)}")

    if dry_run:
        print("\n[dry-run] no changes applied.")
        return

    policy_json = json.dumps(new_policy)
    cmd = [
        "aws",
        "iam",
        "put-role-policy",
        "--role-name",
        ROLE_NAME,
        "--policy-name",
        POLICY_NAME,
        "--policy-document",
        policy_json,
    ]
    if profile:
        cmd = ["aws", "--profile", profile] + cmd[1:]

    _run(cmd)
    print(f"\n[OK] Policy '{POLICY_NAME}' applied to role '{ROLE_NAME}'.")
    print("DEV deploy should now be unblocked. Trigger a deploy to verify.")


if __name__ == "__main__":
    main()
