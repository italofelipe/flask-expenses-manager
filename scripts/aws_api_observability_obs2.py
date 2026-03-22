#!/usr/bin/env python3
"""
Auraxis - API operational baseline (OBS-02) via AWS CLI.

Goal
- Provide a low-cost operational baseline for the API using the signals we
  already publish today.

Scope
1) Create/overwrite a CloudWatch dashboard with:
   - CPU, memory and disk for DEV/PROD
   - Logs Insights widgets for 5xx and p95 latency by route
   - Billing webhook signature anomalies
2) Create a single low-noise log-derived alarm for invalid billing webhook
   signatures in PROD.

Cost posture
- Reuse existing metrics first (`AWS/EC2`, `Auraxis/EC2`, Route53/SNS).
- Keep new custom metrics to the minimum: one log-derived metric for prod
  invalid webhook signatures.
- Logs Insights widgets are meant for on-demand troubleshooting, not 24/7
  wallboard auto-refresh.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from typing import Any

DEFAULT_PROFILE = "auraxis-admin"
DEFAULT_REGION = "us-east-1"

DEFAULT_SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:765480282720:auraxis-alerts"
DEFAULT_NAMESPACE = "Auraxis/API"
DEFAULT_DASHBOARD_NAME = "Auraxis-API-Operations"

DEFAULT_PROD_INSTANCE_ID = "i-0057e3b52162f78f8"
DEFAULT_DEV_INSTANCE_ID = "i-0bddcfc8ea56c2ba3"

DEFAULT_PROD_LOG_GROUP = "/auraxis/prod/containers"
DEFAULT_DEV_LOG_GROUP = "/auraxis/dev/containers"

DEFAULT_PROD_INVALID_SIGNATURE_METRIC = "billing_webhook_invalid_signature_prod"
DEFAULT_PROD_INVALID_SIGNATURE_FILTER = "auraxis-billing-webhook-invalid-signature-prod"
DEFAULT_PROD_INVALID_SIGNATURE_ALARM = "auraxis-billing-webhook-invalid-signature-prod"

EC2_NAMESPACE = "AWS/EC2"
HOST_NAMESPACE = "Auraxis/EC2"

HTTP_OBSERVABILITY_PARSE = (
    " | parse @message "
    '"http_observability request_id=* route=* method=* status=* '
    'duration_ms=* source_framework=* auth_subject=*" as '
    "request_id, route, method, status, duration_ms, source_framework, "
    "auth_subject\n"
)


@dataclass(frozen=True)
class AwsCtx:
    profile: str
    region: str


class AwsCliError(RuntimeError):
    """Raised when an AWS CLI invocation fails."""


def _run_aws(ctx: AwsCtx, args: list[str], *, expect_json: bool = True) -> Any:
    cmd = ["aws"]
    if ctx.profile:
        cmd.extend(["--profile", ctx.profile])
    cmd.extend(["--region", ctx.region, *args])
    process = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        raise AwsCliError(
            (process.stderr or "").strip() or f"AWS CLI failed: {' '.join(cmd)}"
        )
    if not expect_json:
        return process.stdout
    stdout = (process.stdout or "").strip()
    if not stdout:
        return {}
    return json.loads(stdout)


def _metric_widget(
    *,
    title: str,
    metrics: list[list[Any]],
    region: str,
    x: int,
    y: int,
    width: int = 12,
    height: int = 6,
    stat: str = "Average",
    period: int = 60,
    y_min: int | None = None,
    y_max: int | None = None,
) -> dict[str, Any]:
    y_axis: dict[str, Any] = {}
    if y_min is not None or y_max is not None:
        left: dict[str, Any] = {}
        if y_min is not None:
            left["min"] = y_min
        if y_max is not None:
            left["max"] = y_max
        y_axis["left"] = left

    properties: dict[str, Any] = {
        "region": region,
        "title": title,
        "view": "timeSeries",
        "stat": stat,
        "period": period,
        "metrics": metrics,
    }
    if y_axis:
        properties["yAxis"] = y_axis

    return {
        "type": "metric",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "properties": properties,
    }


def _log_widget(
    *,
    title: str,
    log_group: str,
    query_suffix: str,
    region: str,
    x: int,
    y: int,
    width: int = 12,
    height: int = 6,
    view: str = "table",
) -> dict[str, Any]:
    query = f"SOURCE '{log_group}'\n{query_suffix}"
    return {
        "type": "log",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "properties": {
            "region": region,
            "title": title,
            "query": query,
            "view": view,
        },
    }


def build_dashboard_body(
    *,
    region: str,
    dev_instance_id: str,
    prod_instance_id: str,
    dev_log_group: str,
    prod_log_group: str,
) -> dict[str, Any]:
    widgets: list[dict[str, Any]] = [
        _metric_widget(
            title=f"DEV host baseline ({dev_instance_id})",
            metrics=[
                [EC2_NAMESPACE, "CPUUtilization", "InstanceId", dev_instance_id],
                [HOST_NAMESPACE, "mem_used_percent", "InstanceId", dev_instance_id],
                [
                    HOST_NAMESPACE,
                    "disk_used_percent",
                    "InstanceId",
                    dev_instance_id,
                    "path",
                    "/",
                ],
            ],
            region=region,
            x=0,
            y=0,
            y_min=0,
            y_max=100,
        ),
        _metric_widget(
            title=f"PROD host baseline ({prod_instance_id})",
            metrics=[
                [EC2_NAMESPACE, "CPUUtilization", "InstanceId", prod_instance_id],
                [HOST_NAMESPACE, "mem_used_percent", "InstanceId", prod_instance_id],
                [
                    HOST_NAMESPACE,
                    "disk_used_percent",
                    "InstanceId",
                    prod_instance_id,
                    "path",
                    "/",
                ],
            ],
            region=region,
            x=12,
            y=0,
            y_min=0,
            y_max=100,
        ),
        _log_widget(
            title="PROD 5xx by route (24h)",
            log_group=prod_log_group,
            region=region,
            x=0,
            y=6,
            query_suffix=(
                "fields @timestamp, @message\n"
                + " | filter @message like /http_observability/\n"
                + HTTP_OBSERVABILITY_PARSE
                + " | filter toNumber(status) >= 500\n"
                + " | stats count() as errors by route\n"
                + " | sort errors desc\n"
                + " | limit 15"
            ),
        ),
        _log_widget(
            title="PROD p95 latency by route (24h)",
            log_group=prod_log_group,
            region=region,
            x=12,
            y=6,
            query_suffix=(
                "fields @timestamp, @message\n"
                + " | filter @message like /http_observability/\n"
                + HTTP_OBSERVABILITY_PARSE
                + " | stats pct(toNumber(duration_ms), 95) as p95_ms,\n"
                + "    count() as requests by route\n"
                + " | sort p95_ms desc\n"
                + " | limit 15"
            ),
        ),
        _log_widget(
            title="DEV 5xx by route (24h)",
            log_group=dev_log_group,
            region=region,
            x=0,
            y=12,
            query_suffix=(
                "fields @timestamp, @message\n"
                + " | filter @message like /http_observability/\n"
                + HTTP_OBSERVABILITY_PARSE
                + " | filter toNumber(status) >= 500\n"
                + " | stats count() as errors by route\n"
                + " | sort errors desc\n"
                + " | limit 15"
            ),
        ),
        _log_widget(
            title="DEV p95 latency by route (24h)",
            log_group=dev_log_group,
            region=region,
            x=12,
            y=12,
            query_suffix=(
                "fields @timestamp, @message\n"
                + " | filter @message like /http_observability/\n"
                + HTTP_OBSERVABILITY_PARSE
                + " | stats pct(toNumber(duration_ms), 95) as p95_ms,\n"
                + "    count() as requests by route\n"
                + " | sort p95_ms desc\n"
                + " | limit 15"
            ),
        ),
        _log_widget(
            title="PROD billing webhook invalid signature (24h)",
            log_group=prod_log_group,
            region=region,
            x=0,
            y=18,
            query_suffix=(
                "fields @timestamp, @message\n"
                + " | filter @message like /Billing webhook invalid signature/\n"
                + " | stats count() as invalid_signatures by bin(5m)\n"
                + " | sort @timestamp desc\n"
                + " | limit 50"
            ),
            view="timeSeries",
        ),
    ]
    return {"start": "-PT24H", "periodOverride": "inherit", "widgets": widgets}


def put_dashboard(
    ctx: AwsCtx,
    *,
    dashboard_name: str,
    body: dict[str, Any],
) -> None:
    _run_aws(
        ctx,
        [
            "cloudwatch",
            "put-dashboard",
            "--dashboard-name",
            dashboard_name,
            "--dashboard-body",
            json.dumps(body),
        ],
        expect_json=False,
    )


def ensure_invalid_signature_metric_filter(
    ctx: AwsCtx,
    *,
    log_group_name: str,
    filter_name: str,
    namespace: str,
    metric_name: str,
) -> None:
    _run_aws(
        ctx,
        [
            "logs",
            "put-metric-filter",
            "--log-group-name",
            log_group_name,
            "--filter-name",
            filter_name,
            "--filter-pattern",
            '"Billing webhook invalid signature"',
            "--metric-transformations",
            json.dumps(
                [
                    {
                        "metricName": metric_name,
                        "metricNamespace": namespace,
                        "metricValue": "1",
                    }
                ]
            ),
        ],
        expect_json=False,
    )


def ensure_invalid_signature_alarm(
    ctx: AwsCtx,
    *,
    namespace: str,
    metric_name: str,
    alarm_name: str,
    sns_topic_arn: str,
) -> None:
    _run_aws(
        ctx,
        [
            "cloudwatch",
            "put-metric-alarm",
            "--alarm-name",
            alarm_name,
            "--alarm-description",
            (
                "Auraxis: invalid billing webhook signatures detected in PROD. "
                "Investigate spoofing, stale secret or provider misconfiguration."
            ),
            "--namespace",
            namespace,
            "--metric-name",
            metric_name,
            "--statistic",
            "Sum",
            "--period",
            "300",
            "--evaluation-periods",
            "1",
            "--datapoints-to-alarm",
            "1",
            "--threshold",
            "1",
            "--comparison-operator",
            "GreaterThanOrEqualToThreshold",
            "--treat-missing-data",
            "notBreaching",
            "--alarm-actions",
            sns_topic_arn,
            "--ok-actions",
            sns_topic_arn,
        ],
        expect_json=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auraxis API operational baseline")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--sns-topic-arn", default=DEFAULT_SNS_TOPIC_ARN)
    parser.add_argument("--dashboard-name", default=DEFAULT_DASHBOARD_NAME)
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--dev-instance-id", default=DEFAULT_DEV_INSTANCE_ID)
    parser.add_argument("--prod-instance-id", default=DEFAULT_PROD_INSTANCE_ID)
    parser.add_argument("--dev-log-group", default=DEFAULT_DEV_LOG_GROUP)
    parser.add_argument("--prod-log-group", default=DEFAULT_PROD_LOG_GROUP)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dashboard", help="Create/overwrite the API operational dashboard.")
    sub.add_parser(
        "billing-alarm",
        help="Create/overwrite the PROD invalid billing webhook signature alarm.",
    )
    sub.add_parser("apply", help="Apply dashboard + billing invalid signature alarm.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ctx = AwsCtx(profile=args.profile, region=args.region)

    if args.cmd in {"dashboard", "apply"}:
        dashboard_body = build_dashboard_body(
            region=ctx.region,
            dev_instance_id=args.dev_instance_id,
            prod_instance_id=args.prod_instance_id,
            dev_log_group=args.dev_log_group,
            prod_log_group=args.prod_log_group,
        )
        put_dashboard(ctx, dashboard_name=args.dashboard_name, body=dashboard_body)

    if args.cmd in {"billing-alarm", "apply"}:
        ensure_invalid_signature_metric_filter(
            ctx,
            log_group_name=args.prod_log_group,
            filter_name=DEFAULT_PROD_INVALID_SIGNATURE_FILTER,
            namespace=args.namespace,
            metric_name=DEFAULT_PROD_INVALID_SIGNATURE_METRIC,
        )
        ensure_invalid_signature_alarm(
            ctx,
            namespace=args.namespace,
            metric_name=DEFAULT_PROD_INVALID_SIGNATURE_METRIC,
            alarm_name=DEFAULT_PROD_INVALID_SIGNATURE_ALARM,
            sns_topic_arn=args.sns_topic_arn,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
