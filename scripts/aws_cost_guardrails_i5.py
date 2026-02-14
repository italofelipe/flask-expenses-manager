#!/usr/bin/env python3
"""
Auraxis - Cost guardrails (I5).

Important
- AWS Budgets are NOT a hard spending cap. They provide alerts (and optionally
  automated actions if configured) to help you react before costs exceed a target.
- To honor the "never spend more than R$70/month" requirement, we use a
  conservative USD budget limit and early alert thresholds.

What this script does
- Creates or updates an AWS Budgets monthly cost budget (USD).
- Configures email notifications for ACTUAL and FORECASTED spend thresholds.
- Optionally creates a Cost Anomaly Detection monitor + subscription (SNS).

This script is safe to run multiple times (idempotent-ish).
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from typing import Any

DEFAULT_PROFILE = "auraxis-admin"
DEFAULT_REGION = "us-east-1"

DEFAULT_BUDGET_NAME = "auraxis-monthly-budget"
DEFAULT_ANOMALY_MONITOR_NAME = "auraxis-cost-anomaly-monitor"
DEFAULT_ANOMALY_SUBSCRIPTION_NAME = "auraxis-cost-anomaly-subscription"

# Conservative default:
# R$70/month is often around <= $14 USD depending on FX.
# We'll set $10 unless overridden.
DEFAULT_USD_LIMIT = "10"

DEFAULT_EMAIL = "felipe.italo@hotmail.com"
DEFAULT_SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:765480282720:auraxis-alerts"


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


def _account_id(ctx: AwsCtx) -> str:
    out = _run_aws(ctx, ["sts", "get-caller-identity"])
    return str(out["Account"])


def _budget_payload(*, name: str, usd_limit: str) -> dict[str, Any]:
    return {
        "BudgetName": name,
        "BudgetLimit": {"Amount": usd_limit, "Unit": "USD"},
        "BudgetType": "COST",
        "TimeUnit": "MONTHLY",
        "CostTypes": {
            "IncludeTax": True,
            "IncludeSubscription": True,
            "UseBlended": False,
            "IncludeRefund": False,
            "IncludeCredit": False,
            "IncludeUpfront": True,
            "IncludeRecurring": True,
            "IncludeOtherSubscription": True,
            "IncludeSupport": True,
            "IncludeDiscount": True,
            "UseAmortized": True,
        },
    }


def _notification_payload(
    *, notification_type: str, threshold: float
) -> dict[str, Any]:
    return {
        "NotificationType": notification_type,  # ACTUAL | FORECASTED
        "ComparisonOperator": "GREATER_THAN",
        "Threshold": threshold,
        "ThresholdType": "PERCENTAGE",
    }


def _subscriber_email(email: str) -> dict[str, Any]:
    return {"SubscriptionType": "EMAIL", "Address": email}


def create_or_update_budget(
    ctx: AwsCtx,
    *,
    budget_name: str,
    usd_limit: str,
    email: str,
) -> None:
    account = _account_id(ctx)
    budget = _budget_payload(name=budget_name, usd_limit=usd_limit)

    # Create or update budget.
    try:
        _run_aws(
            ctx,
            [
                "budgets",
                "create-budget",
                "--account-id",
                account,
                "--budget",
                json.dumps(budget),
            ],
        )
        created = True
    except AwsCliError as exc:
        # If it already exists, update it.
        if "DuplicateRecordException" not in str(exc):
            raise
        _run_aws(
            ctx,
            [
                "budgets",
                "update-budget",
                "--account-id",
                account,
                "--new-budget",
                json.dumps(budget),
            ],
        )
        created = False

    # Notifications: early and strict.
    # - ACTUAL >= 80%
    # - FORECASTED >= 100%
    notifs = [
        ("ACTUAL", 80.0),
        ("FORECASTED", 100.0),
    ]
    for ntype, threshold in notifs:
        notif = _notification_payload(notification_type=ntype, threshold=threshold)
        subs = [_subscriber_email(email)]
        try:
            _run_aws(
                ctx,
                [
                    "budgets",
                    "create-notification",
                    "--account-id",
                    account,
                    "--budget-name",
                    budget_name,
                    "--notification",
                    json.dumps(notif),
                    "--subscribers",
                    json.dumps(subs),
                ],
            )
        except AwsCliError as exc:
            # Duplicate notifications are fine; keep idempotent behavior.
            if "DuplicateRecordException" not in str(exc):
                raise

    print(
        json.dumps(
            {
                "budget": budget_name,
                "account": account,
                "usd_limit": usd_limit,
                "email": email,
                "created": created,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _ensure_anomaly_monitor(ctx: AwsCtx, *, name: str) -> str:
    out = _run_aws(ctx, ["ce", "get-anomaly-monitors"])
    for m in out.get("AnomalyMonitors", []) or []:
        if str(m.get("MonitorName")) == name:
            return str(m.get("MonitorArn"))
    # Many accounts have a default services monitor and quotas can be tight.
    # If creation is blocked by quota, fall back to the existing default monitor.
    for m in out.get("AnomalyMonitors", []) or []:
        if str(m.get("MonitorName")) == "Default-Services-Monitor":
            return str(m.get("MonitorArn"))
    created = _run_aws(
        ctx,
        [
            "ce",
            "create-anomaly-monitor",
            "--anomaly-monitor",
            json.dumps(
                {
                    "MonitorName": name,
                    "MonitorType": "DIMENSIONAL",
                    "MonitorDimension": "SERVICE",
                }
            ),
        ],
    )
    return str(created["MonitorArn"])


def _ensure_anomaly_subscription(
    ctx: AwsCtx,
    *,
    name: str,
    monitor_arn: str,
    email: str,
) -> str:
    out = _run_aws(ctx, ["ce", "get-anomaly-subscriptions"])
    for s in out.get("AnomalySubscriptions", []) or []:
        if str(s.get("SubscriptionName")) == name:
            return str(s.get("SubscriptionArn"))
    created = _run_aws(
        ctx,
        [
            "ce",
            "create-anomaly-subscription",
            "--anomaly-subscription",
            json.dumps(
                {
                    "SubscriptionName": name,
                    "Threshold": 5.0,  # USD anomaly threshold
                    "Frequency": "DAILY",
                    "MonitorArnList": [monitor_arn],
                    # Cost Explorer API limitation: daily/weekly supports email only.
                    "Subscribers": [{"Type": "EMAIL", "Address": email}],
                }
            ),
        ],
    )
    return str(created["SubscriptionArn"])


def configure_anomaly_detection(
    ctx: AwsCtx, *, monitor_name: str, subscription_name: str, email: str
) -> None:
    mon_arn = _ensure_anomaly_monitor(ctx, name=monitor_name)
    sub_arn = _ensure_anomaly_subscription(
        ctx,
        name=subscription_name,
        monitor_arn=mon_arn,
        email=email,
    )
    print(
        json.dumps(
            {"monitor_arn": mon_arn, "subscription_arn": sub_arn},
            indent=2,
            sort_keys=True,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Auraxis cost guardrails (I5)")
    p.add_argument("--profile", default=DEFAULT_PROFILE)
    p.add_argument("--region", default=DEFAULT_REGION)
    p.add_argument("--budget-name", default=DEFAULT_BUDGET_NAME)
    p.add_argument("--usd-limit", default=DEFAULT_USD_LIMIT)
    p.add_argument("--email", default=DEFAULT_EMAIL)
    p.add_argument("--enable-anomaly-detection", action="store_true")
    return p


def main() -> int:
    args = build_parser().parse_args()
    ctx = AwsCtx(profile=args.profile, region=args.region)

    create_or_update_budget(
        ctx,
        budget_name=str(args.budget_name),
        usd_limit=str(args.usd_limit),
        email=str(args.email),
    )

    if bool(args.enable_anomaly_detection):
        configure_anomaly_detection(
            ctx,
            monitor_name=DEFAULT_ANOMALY_MONITOR_NAME,
            subscription_name=DEFAULT_ANOMALY_SUBSCRIPTION_NAME,
            email=str(args.email),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
