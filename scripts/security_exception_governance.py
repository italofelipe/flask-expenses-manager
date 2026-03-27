#!/usr/bin/env python3
"""Canonical governance for security exceptions used in local and CI checks."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "security_exception_allowlist.json"
SUPPORTED_TOOLS = frozenset({"pip-audit", "osv-scanner"})


class SecurityExceptionGovernanceError(Exception):
    """Raised when the canonical exception inventory is invalid."""


@dataclass(frozen=True)
class SecurityException:
    id: str
    tools: tuple[str, ...]
    owner: str
    reviewed_at: str
    justification: str


def _load_raw_config(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SecurityExceptionGovernanceError(
            f"Missing security exception config: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise SecurityExceptionGovernanceError(
            f"Invalid JSON in security exception config: {path}"
        ) from exc

    if not isinstance(raw, dict):
        raise SecurityExceptionGovernanceError(
            "Security exception config must be a JSON object"
        )
    return raw


def _require_string(
    item: dict[str, Any],
    *,
    field_name: str,
    exception_id: str,
) -> str:
    value = str(item.get(field_name) or "").strip()
    if not value:
        raise SecurityExceptionGovernanceError(
            f"Exception {exception_id} must define {field_name}"
        )
    return value


def _parse_tools(item: dict[str, Any], *, exception_id: str) -> tuple[str, ...]:
    tools_raw = item.get("tools")
    if not isinstance(tools_raw, list) or not tools_raw:
        raise SecurityExceptionGovernanceError(
            f"Exception {exception_id} must define a non-empty tools list"
        )
    tools = tuple(str(tool).strip() for tool in tools_raw if str(tool).strip())
    if not tools:
        raise SecurityExceptionGovernanceError(
            f"Exception {exception_id} must define at least one valid tool"
        )
    unknown_tools = sorted(set(tools) - SUPPORTED_TOOLS)
    if unknown_tools:
        unknown_label = ", ".join(unknown_tools)
        raise SecurityExceptionGovernanceError(
            f"Exception {exception_id} uses unsupported tools: {unknown_label}"
        )
    return tools


def _parse_exception_item(
    item: dict[str, Any],
    *,
    index: int,
    seen_ids: set[str],
) -> SecurityException:
    exception_id = str(item.get("id") or "").strip()
    if not exception_id:
        raise SecurityExceptionGovernanceError(
            f"Exception entry #{index} must define a non-empty id"
        )
    if exception_id in seen_ids:
        raise SecurityExceptionGovernanceError(
            f"Duplicate security exception id: {exception_id}"
        )
    seen_ids.add(exception_id)

    tools = _parse_tools(item, exception_id=exception_id)
    owner = _require_string(item, field_name="owner", exception_id=exception_id)
    reviewed_at = _require_string(
        item,
        field_name="reviewed_at",
        exception_id=exception_id,
    )
    try:
        date.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise SecurityExceptionGovernanceError(
            f"Exception {exception_id} has invalid reviewed_at: {reviewed_at}"
        ) from exc

    justification = _require_string(
        item,
        field_name="justification",
        exception_id=exception_id,
    )
    return SecurityException(
        id=exception_id,
        tools=tools,
        owner=owner,
        reviewed_at=reviewed_at,
        justification=justification,
    )


def load_security_exceptions(
    path: Path = DEFAULT_CONFIG_PATH,
) -> list[SecurityException]:
    raw = _load_raw_config(path)
    exceptions_raw = raw.get("exceptions")
    if not isinstance(exceptions_raw, list):
        raise SecurityExceptionGovernanceError(
            "Security exception config must define an 'exceptions' list"
        )

    seen_ids: set[str] = set()
    exceptions: list[SecurityException] = []

    for index, item in enumerate(exceptions_raw, start=1):
        if not isinstance(item, dict):
            raise SecurityExceptionGovernanceError(
                f"Exception entry #{index} must be an object"
            )
        exceptions.append(_parse_exception_item(item, index=index, seen_ids=seen_ids))

    return exceptions


def _ids_for_tool(exceptions: list[SecurityException], tool: str) -> list[str]:
    if tool not in SUPPORTED_TOOLS:
        raise SecurityExceptionGovernanceError(f"Unsupported tool: {tool}")
    return sorted(
        exception.id for exception in exceptions if tool in set(exception.tools)
    )


def build_pip_audit_args(exceptions: list[SecurityException]) -> list[str]:
    args: list[str] = []
    for exception_id in _ids_for_tool(exceptions, "pip-audit"):
        args.extend(["--ignore-vuln", exception_id])
    return args


def build_osv_allowlist(exceptions: list[SecurityException]) -> str:
    return ",".join(_ids_for_tool(exceptions, "osv-scanner"))


def _build_summary(exceptions: list[SecurityException]) -> str:
    lines = ["# Security Exception Governance", ""]
    if not exceptions:
        lines.append("- No active exceptions.")
        return "\n".join(lines)

    for exception in exceptions:
        lines.append(
            f"- `{exception.id}` via {', '.join(exception.tools)} "
            f"(owner={exception.owner}, reviewed_at={exception.reviewed_at})"
        )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Govern canonical security exceptions for CI and local checks."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the canonical security exception allowlist JSON.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="Validate the canonical exception inventory.")
    subparsers.add_parser(
        "pip-audit-args",
        help="Emit canonical --ignore-vuln flags for pip-audit.",
    )
    subparsers.add_parser(
        "osv-allowlist",
        help="Emit the canonical comma-separated allowlist for OSV-Scanner.",
    )
    subparsers.add_parser(
        "summary",
        help="Print a human-readable summary of active security exceptions.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    exceptions = load_security_exceptions(args.config)

    if args.command == "check":
        print(
            f"[security-exception-governance] ok: {len(exceptions)} active exception(s)"
        )
        return 0
    if args.command == "pip-audit-args":
        print(" ".join(build_pip_audit_args(exceptions)))
        return 0
    if args.command == "osv-allowlist":
        print(build_osv_allowlist(exceptions))
        return 0
    if args.command == "summary":
        print(_build_summary(exceptions))
        return 0

    raise SecurityExceptionGovernanceError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SecurityExceptionGovernanceError as exc:
        print(f"[security-exception-governance] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
