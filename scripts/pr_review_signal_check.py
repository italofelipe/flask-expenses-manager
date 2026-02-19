#!/usr/bin/env python3
"""Evaluate Cursor Bugbot review signal on pull requests.

This script reads review threads from GitHub GraphQL API and summarizes
findings posted by configured bot logins (default: Cursor Bugbot aliases).

Modes:
- advisory: never fails; prints a summary signal for maintainers.
- strict: fails when unresolved high/critical findings exist.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GRAPHQL_URL = "https://api.github.com/graphql"
DEFAULT_BOT_LOGINS = ("cursor[bot]", "cursor-ai[bot]", "cursor-bot[bot]")
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
SEVERITY_PATTERN = re.compile(
    r"\b(critical|high|medium|low)\s+severity\b", re.IGNORECASE
)
REVIEW_THREADS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        nodes {
          isResolved
          isOutdated
          comments(first: 20) {
            nodes {
              bodyText
              url
              author {
                login
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""


class ReviewSignalError(Exception):
    """Raised when API calls or payload parsing fail."""


@dataclass(frozen=True)
class Finding:
    severity: str
    resolved: bool
    outdated: bool
    author: str
    excerpt: str
    url: str


def _github_graphql(
    token: str, query: str, variables: dict[str, Any]
) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "auraxis-pr-review-signal",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:  # pragma: no cover - network-dependent path
        detail = exc.read().decode("utf-8", errors="replace")
        raise ReviewSignalError(f"GitHub GraphQL HTTP {exc.code}: {detail}") from exc
    except URLError as exc:  # pragma: no cover - network-dependent path
        raise ReviewSignalError(
            f"GitHub GraphQL connection error: {exc.reason}"
        ) from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReviewSignalError("Invalid JSON response from GitHub GraphQL") from exc

    errors = parsed.get("errors")
    if isinstance(errors, list) and errors:
        raise ReviewSignalError(f"GitHub GraphQL errors: {errors}")
    data = parsed.get("data")
    if not isinstance(data, dict):
        raise ReviewSignalError("Missing 'data' payload from GitHub GraphQL")
    return data


def _extract_severity(text: str) -> str | None:
    match = SEVERITY_PATTERN.search(text)
    if not match:
        return None
    return match.group(1).lower()


def _best_finding_in_thread(
    thread: dict[str, Any],
    bot_logins: set[str],
) -> Finding | None:
    comments = (
        thread.get("comments", {}).get("nodes", [])
        if isinstance(thread.get("comments"), dict)
        else []
    )
    resolved = bool(thread.get("isResolved"))
    outdated = bool(thread.get("isOutdated"))

    best: Finding | None = None
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        author = comment.get("author") or {}
        login = (author.get("login") if isinstance(author, dict) else None) or ""
        if login.lower() not in bot_logins:
            continue
        body = str(comment.get("bodyText") or "")
        severity = _extract_severity(body)
        if severity is None:
            continue
        url = str(comment.get("url") or "")
        excerpt = body.replace("\n", " ").strip()
        if len(excerpt) > 180:
            excerpt = f"{excerpt[:177]}..."
        finding = Finding(
            severity=severity,
            resolved=resolved,
            outdated=outdated,
            author=login,
            excerpt=excerpt,
            url=url,
        )
        if (
            best is None
            or SEVERITY_RANK[finding.severity] > SEVERITY_RANK[best.severity]
        ):
            best = finding
    return best


def _extract_review_threads_page(
    data: dict[str, Any],
    *,
    owner: str,
    repo: str,
    pr_number: int,
) -> tuple[list[dict[str, Any]], bool, str | None]:
    repository = data.get("repository")
    if not isinstance(repository, dict):
        raise ReviewSignalError("Repository not found in GraphQL response")
    pull_request = repository.get("pullRequest")
    if not isinstance(pull_request, dict):
        raise ReviewSignalError(
            f"Pull request #{pr_number} not found for {owner}/{repo}"
        )
    review_threads = pull_request.get("reviewThreads")
    if not isinstance(review_threads, dict):
        raise ReviewSignalError("Missing reviewThreads in GraphQL response")

    nodes = review_threads.get("nodes", [])
    page_info = review_threads.get("pageInfo", {})
    has_next = (
        bool(page_info.get("hasNextPage")) if isinstance(page_info, dict) else False
    )
    next_cursor = (
        str(page_info.get("endCursor"))
        if isinstance(page_info, dict) and page_info.get("endCursor")
        else None
    )
    if not isinstance(nodes, list):
        nodes = []
    return nodes, has_next, next_cursor


def _fetch_review_threads_page(
    token: str,
    *,
    owner: str,
    repo: str,
    pr_number: int,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], bool, str | None]:
    data = _github_graphql(
        token,
        REVIEW_THREADS_QUERY,
        {"owner": owner, "repo": repo, "number": pr_number, "cursor": cursor},
    )
    return _extract_review_threads_page(
        data,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
    )


def _collect_findings(
    token: str,
    owner: str,
    repo: str,
    pr_number: int,
    bot_logins: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    cursor: str | None = None
    while True:
        nodes, has_next, next_cursor = _fetch_review_threads_page(
            token,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            cursor=cursor,
        )
        for thread in nodes:
            if not isinstance(thread, dict):
                continue
            finding = _best_finding_in_thread(thread, bot_logins)
            if finding is not None:
                findings.append(finding)
        if not has_next:
            break
        cursor = next_cursor
        if cursor is None:
            break
    return findings


def _format_summary(
    findings: list[Finding],
    mode: str,
    owner: str,
    repo: str,
    pr_number: int,
) -> tuple[list[str], bool]:
    if not findings:
        return (
            [
                "## Cursor Bugbot Review Signal",
                "",
                f"- PR: `{owner}/{repo}#{pr_number}`",
                "- Findings by configured bot logins: `0`",
                "- Status: PASS (no bot findings detected)",
            ],
            False,
        )

    totals: dict[str, int] = {key: 0 for key in SEVERITY_RANK}
    unresolved_high_or_critical = False

    for finding in findings:
        totals[finding.severity] += 1
        if (
            finding.severity in {"high", "critical"}
            and not finding.resolved
            and not finding.outdated
        ):
            unresolved_high_or_critical = True

    lines = [
        "## Cursor Bugbot Review Signal",
        "",
        f"- PR: `{owner}/{repo}#{pr_number}`",
        f"- Findings (all severities): `{len(findings)}`",
        (
            "- Breakdown: "
            f"critical=`{totals['critical']}` "
            f"high=`{totals['high']}` "
            f"medium=`{totals['medium']}` "
            f"low=`{totals['low']}`"
        ),
        f"- Mode: `{mode}`",
    ]

    if unresolved_high_or_critical:
        lines.append("- Status: ATTENTION (unresolved high/critical findings detected)")
    else:
        lines.append("- Status: PASS (no unresolved high/critical findings)")

    lines.append("")
    lines.append("### Sample findings")
    for finding in findings[:8]:
        state = "resolved" if finding.resolved else "open"
        outdated = "outdated" if finding.outdated else "active"
        lines.append(
            f"- `{finding.severity}` `{state}` `{outdated}` by `{finding.author}`: "
            f"{finding.excerpt} ({finding.url})"
        )
    if len(findings) > 8:
        lines.append(f"- ... and {len(findings) - 8} more")

    return lines, unresolved_high_or_critical


def _write_summary(lines: list[str]) -> None:
    payload = "\n".join(lines)
    print(payload)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as summary_file:
        summary_file.write(payload)
        summary_file.write("\n")


def _parse_repo(repo_value: str) -> tuple[str, str]:
    parts = repo_value.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ReviewSignalError(
            f"Invalid repo format '{repo_value}', expected owner/repo"
        )
    return parts[0], parts[1]


def _parse_bot_logins(raw: str) -> set[str]:
    values = {entry.strip().lower() for entry in raw.split(",") if entry.strip()}
    if not values:
        values = set(DEFAULT_BOT_LOGINS)
    return values


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate Cursor Bugbot PR review signal"
    )
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument(
        "--mode",
        choices=("advisory", "strict"),
        default="advisory",
        help="advisory: never fail; strict: fail on unresolved high/critical findings",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable name holding GitHub token",
    )
    parser.add_argument(
        "--bot-logins",
        default=os.getenv("BUGBOT_LOGINS", ",".join(DEFAULT_BOT_LOGINS)),
        help="Comma-separated bot logins to evaluate",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.repo:
        print("Missing --repo (or GITHUB_REPOSITORY).", file=sys.stderr)
        return 2
    if args.pr_number <= 0:
        print("Missing --pr-number (> 0).", file=sys.stderr)
        return 2

    token = os.getenv(args.token_env, "")
    if not token:
        print(f"Missing token in env var '{args.token_env}'.", file=sys.stderr)
        return 2

    try:
        owner, repo = _parse_repo(args.repo)
        bot_logins = _parse_bot_logins(args.bot_logins)
        findings = _collect_findings(token, owner, repo, args.pr_number, bot_logins)
        lines, unresolved_high_or_critical = _format_summary(
            findings=findings,
            mode=args.mode,
            owner=owner,
            repo=repo,
            pr_number=args.pr_number,
        )
        _write_summary(lines)
    except ReviewSignalError as exc:
        print(f"Review signal check failed: {exc}", file=sys.stderr)
        return 2

    if args.mode == "strict" and unresolved_high_or_critical:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
