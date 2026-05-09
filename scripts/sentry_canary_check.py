#!/usr/bin/env python3
"""
Sentry error rate check for canary deploy gating and production watchdog.

Usage:
    python3 scripts/sentry_canary_check.py --project <slug> [options]

Exits 0 (OK) or 1 (ALERT / error).
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

SENTRY_API_BASE = "https://sentry.io/api/0"


def fetch_stats(
    org: str, project: str, token: str, since: int, timeout: int = 10
) -> list:
    """
    Call the Sentry project stats endpoint and return the raw [timestamp, count] list.
    Returns an empty list on failure.
    """
    url = (
        f"{SENTRY_API_BASE}/projects/{org}/{project}/stats/"
        f"?stat=received&resolution=1m&since={since}"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            if not isinstance(data, list):
                print(
                    f"[WARN] Unexpected Sentry response type: {type(data)}",
                    file=sys.stderr,
                )
                return []
            return data
    except urllib.error.HTTPError as exc:
        print(f"[ERROR] Sentry API HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        return []
    except urllib.error.URLError as exc:
        print(f"[ERROR] Sentry API connection error: {exc.reason}", file=sys.stderr)
        return []
    except json.JSONDecodeError as exc:
        print(f"[ERROR] Failed to parse Sentry response: {exc}", file=sys.stderr)
        return []


def average_rate(datapoints: list) -> float:
    """
    Given a list of [timestamp, count] pairs, return the average events/min
    across all non-zero buckets. Returns 0.0 for an empty or all-zero series.
    """
    if not datapoints:
        return 0.0
    counts = [
        entry[1]
        for entry in datapoints
        if isinstance(entry, (list, tuple)) and len(entry) >= 2
    ]
    non_zero = [c for c in counts if c > 0]
    if not non_zero:
        return 0.0
    return sum(non_zero) / len(non_zero)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Sentry error rate against a rolling baseline."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Sentry project slug (required).",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=10,
        help="Minutes to observe for the current rate (default: 10).",
    )
    parser.add_argument(
        "--baseline-window",
        type=int,
        default=60,
        help="Minutes to use for the baseline rate (default: 60).",
    )
    parser.add_argument(
        "--baseline-multiplier",
        type=float,
        default=2.0,
        help="Alert threshold = baseline_rate * multiplier (default: 2.0).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Read required env vars — fail fast with a clear message if absent.
    token = os.environ.get("SENTRY_TOKEN")
    org = os.environ.get("SENTRY_ORG")

    if not token:
        print("[ERROR] SENTRY_TOKEN environment variable is not set.", file=sys.stderr)
        return 1
    if not org:
        print("[ERROR] SENTRY_ORG environment variable is not set.", file=sys.stderr)
        return 1

    now = int(time.time())

    # Baseline window: covers [now - baseline_window_minutes, now - window_minutes]
    baseline_since = now - (args.baseline_window * 60)
    # Current window: covers [now - window_minutes, now]
    current_since = now - (args.window * 60)

    print(f"[INFO] Project  : {org}/{args.project}")
    print(f"[INFO] Baseline : last {args.baseline_window}m  (since {baseline_since})")
    print(f"[INFO] Current  : last {args.window}m           (since {current_since})")
    print(f"[INFO] Multiplier: {args.baseline_multiplier}x")
    print()

    baseline_data = fetch_stats(org, args.project, token, baseline_since)
    current_data = fetch_stats(org, args.project, token, current_since)

    baseline_rate = average_rate(baseline_data)
    current_rate = average_rate(current_data)

    # Threshold: at least 1 event/min floor so a zero-baseline never triggers.
    threshold = max(baseline_rate * args.baseline_multiplier, 1.0)

    print(f"  Baseline rate : {baseline_rate:.2f} events/min")
    print(f"  Current rate  : {current_rate:.2f} events/min")
    mult = args.baseline_multiplier
    print(f"  Threshold     : {threshold:.2f} events/min  (max(baseline*{mult}, 1.0))")
    print()

    if current_rate > threshold:
        print(
            f"[ALERT] Error rate EXCEEDED threshold — "
            f"current={current_rate:.2f} > threshold={threshold:.2f} events/min"
        )
        return 1

    print(
        f"[OK] Error rate within threshold — "
        f"current={current_rate:.2f} <= threshold={threshold:.2f} events/min"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
