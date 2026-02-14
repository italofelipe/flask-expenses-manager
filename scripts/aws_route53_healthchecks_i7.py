#!/usr/bin/env python3
"""
Auraxis - External health checks (I7) via Route 53 + CloudWatch Alarm.

Goal
- Detect full-stack outage (DNS -> TLS -> Nginx -> app) from outside the instance,
  without requiring a 24/7 heavy observability stack.

Why Route 53 Health Checks
- Cheap baseline for small budgets and low-traffic systems.
- Integrates natively with CloudWatch metrics + alarms.
- Works even if the instance is unreachable via SSM/SSH.

What this script does
1) Ensures two health checks exist:
   - PROD: https://api.auraxis.com.br/healthz
   - DEV:  https://dev.api.auraxis.com.br/healthz
2) Creates CloudWatch alarms on `AWS/Route53` `HealthCheckStatus` < 1
   and wires them to the existing SNS topic `auraxis-alerts`.

Prerequisites
- The `/healthz` endpoint must exist and be public.
- AWS CLI authenticated locally (AWS SSO profile recommended).
- SNS topic `auraxis-alerts` exists.

Notes on cost
- Route 53 health checks are billed per check. Keep the number of checks small.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from dataclasses import dataclass
from typing import Any, Optional

DEFAULT_PROFILE = "auraxis-admin"
DEFAULT_REGION = "us-east-1"

DEFAULT_SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:765480282720:auraxis-alerts"

DEFAULT_PROD_DOMAIN = "api.auraxis.com.br"
DEFAULT_DEV_DOMAIN = "dev.api.auraxis.com.br"
DEFAULT_PATH = "/healthz"


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


def _find_health_check_id(
    ctx: AwsCtx, *, fqdn: str, resource_path: str, port: int, type_: str
) -> Optional[str]:
    """
    Best-effort lookup of an existing health check that matches the config.

    AWS does not provide an efficient "get by name", so we scan the list.
    This is acceptable for very small fleets.
    """
    out = _run_aws(ctx, ["route53", "list-health-checks"])
    for item in out.get("HealthChecks") or []:
        cfg = item.get("HealthCheckConfig") or {}
        if (
            str(cfg.get("FullyQualifiedDomainName")) == fqdn
            and str(cfg.get("ResourcePath", "")) == resource_path
            and int(cfg.get("Port") or 0) == port
            and str(cfg.get("Type")) == type_
        ):
            return str(item.get("Id"))
    return None


def ensure_health_check(
    ctx: AwsCtx,
    *,
    fqdn: str,
    resource_path: str,
    port: int = 443,
    type_: str = "HTTPS",
    request_interval: int = 30,
    failure_threshold: int = 3,
) -> str:
    existing = _find_health_check_id(
        ctx, fqdn=fqdn, resource_path=resource_path, port=port, type_=type_
    )
    if existing:
        return existing

    caller_ref = f"auraxis-{fqdn}-{uuid.uuid4().hex}"
    cfg = {
        "FullyQualifiedDomainName": fqdn,
        "Port": port,
        "Type": type_,
        "ResourcePath": resource_path,
        "RequestInterval": request_interval,
        "FailureThreshold": failure_threshold,
    }
    if type_ == "HTTPS":
        # SNI is required when multiple TLS certs share the same IP/ALB.
        cfg["EnableSNI"] = True
    out = _run_aws(
        ctx,
        [
            "route53",
            "create-health-check",
            "--caller-reference",
            caller_ref,
            "--health-check-config",
            json.dumps(cfg),
        ],
    )
    return str((out.get("HealthCheck") or {}).get("Id"))


def ensure_health_alarm(
    ctx: AwsCtx,
    *,
    alarm_name: str,
    health_check_id: str,
    sns_topic_arn: str,
    description: str,
) -> None:
    _run_aws(
        ctx,
        [
            "cloudwatch",
            "put-metric-alarm",
            "--alarm-name",
            alarm_name,
            "--alarm-description",
            description,
            "--namespace",
            "AWS/Route53",
            "--metric-name",
            "HealthCheckStatus",
            "--dimensions",
            f"Name=HealthCheckId,Value={health_check_id}",
            "--statistic",
            "Minimum",
            "--period",
            "60",
            "--evaluation-periods",
            "3",
            "--datapoints-to-alarm",
            "2",
            "--threshold",
            "1",
            "--comparison-operator",
            "LessThanThreshold",
            "--treat-missing-data",
            "breaching",
            "--alarm-actions",
            sns_topic_arn,
            "--ok-actions",
            sns_topic_arn,
            "--insufficient-data-actions",
            sns_topic_arn,
        ],
        expect_json=False,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Auraxis Route 53 health checks (I7)")
    p.add_argument("--profile", default=DEFAULT_PROFILE)
    p.add_argument("--region", default=DEFAULT_REGION)
    p.add_argument("--sns-topic-arn", default=DEFAULT_SNS_TOPIC_ARN)
    p.add_argument("--prod-domain", default=DEFAULT_PROD_DOMAIN)
    p.add_argument("--dev-domain", default=DEFAULT_DEV_DOMAIN)
    p.add_argument("--path", default=DEFAULT_PATH)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("apply", help="Create/ensure health checks + alarms.")
    sub.add_parser("validate", help="Validate health checks exist (best-effort).")
    sub.add_parser(
        "disable-actions",
        help=(
            "Disable alarm actions for auraxis-health-dev/prod "
            "(prevents notifications)."
        ),
    )
    sub.add_parser(
        "enable-actions",
        help=(
            "Enable alarm actions for auraxis-health-dev/prod "
            "(restores notifications)."
        ),
    )
    sub.add_parser(
        "migrate-dev-http",
        help=(
            "Update DEV health check to HTTP:80 (keeps PROD on HTTPS:443). "
            "Useful when DEV does not have a TLS cert yet."
        ),
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    ctx = AwsCtx(profile=args.profile, region=args.region)

    if args.cmd == "apply":
        prod_id = ensure_health_check(
            ctx, fqdn=args.prod_domain, resource_path=args.path
        )
        dev_id = ensure_health_check(ctx, fqdn=args.dev_domain, resource_path=args.path)

        ensure_health_alarm(
            ctx,
            alarm_name="auraxis-health-prod",
            health_check_id=prod_id,
            sns_topic_arn=args.sns_topic_arn,
            description=(
                "Auraxis PROD health check failing: "
                f"https://{args.prod_domain}{args.path}"
            ),
        )
        ensure_health_alarm(
            ctx,
            alarm_name="auraxis-health-dev",
            health_check_id=dev_id,
            sns_topic_arn=args.sns_topic_arn,
            description=(
                "Auraxis DEV health check failing: "
                f"https://{args.dev_domain}{args.path}"
            ),
        )
        return 0

    if args.cmd == "validate":
        for fqdn in (args.prod_domain, args.dev_domain):
            found = _find_health_check_id(
                ctx, fqdn=fqdn, resource_path=args.path, port=443, type_="HTTPS"
            )
            if not found:
                raise AwsCliError(f"Missing health check for https://{fqdn}{args.path}")
        return 0

    if args.cmd == "disable-actions":
        _run_aws(
            ctx,
            [
                "cloudwatch",
                "disable-alarm-actions",
                "--alarm-names",
                "auraxis-health-prod",
                "auraxis-health-dev",
            ],
            expect_json=False,
        )
        return 0

    if args.cmd == "enable-actions":
        _run_aws(
            ctx,
            [
                "cloudwatch",
                "enable-alarm-actions",
                "--alarm-names",
                "auraxis-health-prod",
                "auraxis-health-dev",
            ],
            expect_json=False,
        )
        return 0

    if args.cmd == "migrate-dev-http":
        https_id = _find_health_check_id(
            ctx,
            fqdn=args.dev_domain,
            resource_path=args.path,
            port=443,
            type_="HTTPS",
        )
        http_id = _find_health_check_id(
            ctx,
            fqdn=args.dev_domain,
            resource_path=args.path,
            port=80,
            type_="HTTP",
        )
        if not http_id:
            http_id = ensure_health_check(
                ctx,
                fqdn=args.dev_domain,
                resource_path=args.path,
                port=80,
                type_="HTTP",
            )

        ensure_health_alarm(
            ctx,
            alarm_name="auraxis-health-dev",
            health_check_id=http_id,
            sns_topic_arn=args.sns_topic_arn,
            description=(
                "Auraxis DEV health check failing: "
                f"http://{args.dev_domain}{args.path}"
            ),
        )

        # Disable the old HTTPS check to avoid confusion and reduce noise.
        if https_id and https_id != http_id:
            _run_aws(
                ctx,
                [
                    "route53",
                    "update-health-check",
                    "--health-check-id",
                    https_id,
                    "--disabled",
                ],
                expect_json=False,
            )
        return 0

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
