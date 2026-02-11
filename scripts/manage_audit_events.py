#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from app import create_app
from app.services.audit_event_service import (
    purge_expired_audit_events,
    search_audit_events_by_request_id,
    serialize_audit_event,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Operational helpers for persisted audit events.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser(
        "search",
        help="Search persisted audit events by request_id.",
    )
    search_parser.add_argument("--request-id", required=True)
    search_parser.add_argument("--limit", type=int, default=100)

    purge_parser = subparsers.add_parser(
        "purge",
        help="Delete persisted audit events older than retention window.",
    )
    purge_parser.add_argument("--retention-days", type=int, default=90)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.command == "search":
            events = search_audit_events_by_request_id(
                str(args.request_id),
                limit=int(args.limit),
            )
            payload = {
                "request_id": str(args.request_id),
                "count": len(events),
                "items": [serialize_audit_event(event) for event in events],
            }
            print(json.dumps(payload, ensure_ascii=True, indent=2))
            return 0

        if args.command == "purge":
            deleted = purge_expired_audit_events(
                retention_days=int(args.retention_days)
            )
            print(
                json.dumps(
                    {
                        "retention_days": int(args.retention_days),
                        "deleted": deleted,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
            )
            return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
