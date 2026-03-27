#!/usr/bin/env python3
"""Traceability helpers for pull requests and post-merge absorption.

This script is intentionally lightweight so it can run both in CI and by hand
while investigating merge/release ambiguity.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GRAPHQL_URL = "https://api.github.com/graphql"
DEFAULT_BASE_BRANCHES = ("master", "main", "develop")
PULL_REQUEST_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      title
      url
      state
      isDraft
      mergeable
      mergeStateStatus
      baseRefName
      headRefName
      headRefOid
      mergedAt
      mergeCommit {
        oid
      }
    }
  }
}
"""


class TraceabilityError(Exception):
    """Raised when GitHub or git state cannot be evaluated."""


@dataclass(frozen=True)
class PullRequestTrace:
    number: int
    title: str
    url: str
    state: str
    is_draft: bool
    mergeable: str
    merge_state_status: str
    base_ref_name: str
    head_ref_name: str
    head_ref_oid: str
    merged_at: str | None
    merge_commit_oid: str | None

    @property
    def is_release_pr(self) -> bool:
        return self.head_ref_name.startswith(
            "release-please--"
        ) or self.title.startswith("chore(master): release")

    @property
    def is_stacked_pr(self) -> bool:
        return self.base_ref_name not in DEFAULT_BASE_BRANCHES

    @property
    def absorption_commit_oid(self) -> str:
        return self.merge_commit_oid or self.head_ref_oid


def _github_graphql(
    token: str,
    query: str,
    variables: dict[str, Any],
) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "auraxis-pr-traceability",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:  # pragma: no cover - network-dependent
        detail = exc.read().decode("utf-8", errors="replace")
        raise TraceabilityError(f"GitHub GraphQL HTTP {exc.code}: {detail}") from exc
    except URLError as exc:  # pragma: no cover - network-dependent
        raise TraceabilityError(
            f"GitHub GraphQL connection error: {exc.reason}"
        ) from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TraceabilityError("Invalid JSON response from GitHub GraphQL") from exc

    errors = parsed.get("errors")
    if isinstance(errors, list) and errors:
        raise TraceabilityError(f"GitHub GraphQL errors: {errors}")

    data = parsed.get("data")
    if not isinstance(data, dict):
        raise TraceabilityError("Missing 'data' payload from GitHub GraphQL")
    return data


def _parse_repository(repo: str) -> tuple[str, str]:
    try:
        owner, name = repo.split("/", 1)
    except ValueError as exc:
        raise TraceabilityError("Repository must use owner/name format") from exc
    return owner, name


def _extract_pull_request(
    data: dict[str, Any], *, repo: str, pr_number: int
) -> PullRequestTrace:
    repository = data.get("repository")
    if not isinstance(repository, dict):
        raise TraceabilityError("Repository not found in GraphQL response")
    pull_request = repository.get("pullRequest")
    if not isinstance(pull_request, dict):
        raise TraceabilityError(f"Pull request #{pr_number} not found for {repo}")

    merge_commit = pull_request.get("mergeCommit")
    merge_commit_oid = None
    if isinstance(merge_commit, dict) and merge_commit.get("oid"):
        merge_commit_oid = str(merge_commit["oid"])

    return PullRequestTrace(
        number=int(pull_request.get("number") or pr_number),
        title=str(pull_request.get("title") or ""),
        url=str(pull_request.get("url") or ""),
        state=str(pull_request.get("state") or ""),
        is_draft=bool(pull_request.get("isDraft")),
        mergeable=str(pull_request.get("mergeable") or ""),
        merge_state_status=str(pull_request.get("mergeStateStatus") or ""),
        base_ref_name=str(pull_request.get("baseRefName") or ""),
        head_ref_name=str(pull_request.get("headRefName") or ""),
        head_ref_oid=str(pull_request.get("headRefOid") or ""),
        merged_at=(
            str(pull_request.get("mergedAt"))
            if pull_request.get("mergedAt") is not None
            else None
        ),
        merge_commit_oid=merge_commit_oid,
    )


def fetch_pull_request_trace(
    token: str, *, repo: str, pr_number: int
) -> PullRequestTrace:
    owner, name = _parse_repository(repo)
    data = _github_graphql(
        token,
        PULL_REQUEST_QUERY,
        {"owner": owner, "repo": name, "number": pr_number},
    )
    return _extract_pull_request(data, repo=repo, pr_number=pr_number)


def _run_git(args: list[str]) -> None:
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise TraceabilityError(stderr or f"git command failed: {' '.join(args)}")


def verify_absorption_in_master(
    trace: PullRequestTrace,
    *,
    master_ref: str,
    fetch_remote: bool,
) -> str:
    if trace.state != "MERGED":
        raise TraceabilityError(f"PR #{trace.number} is not merged")

    if fetch_remote:
        _run_git(["git", "fetch", "origin"])

    target_sha = trace.absorption_commit_oid
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", target_sha, master_ref],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TraceabilityError(f"Commit {target_sha} is not absorbed in {master_ref}")
    return target_sha


def _format_pr_summary(trace: PullRequestTrace) -> list[str]:
    lines = [
        "## PR Traceability",
        f"- PR: `#{trace.number}`",
        f"- URL: {trace.url}",
        f"- State: `{trace.state}`",
        f"- Mergeable: `{trace.mergeable}`",
        f"- Merge state: `{trace.merge_state_status}`",
        f"- Base: `{trace.base_ref_name}`",
        f"- Head: `{trace.head_ref_name}`",
        f"- Release PR: `{'yes' if trace.is_release_pr else 'no'}`",
        f"- Stacked PR: `{'yes' if trace.is_stacked_pr else 'no'}`",
    ]
    if trace.is_release_pr:
        lines.append("- Policy: release PR must have healthy checks before merge.")
    if trace.is_stacked_pr:
        lines.append(
            "- Policy: confirm absorption in `master` after the merge chain closes."
        )
    return lines


def _write_summary(lines: list[str]) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
        handle.write("\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Traceability checks for API merge/release flow."
    )
    parser.add_argument(
        "--repo", required=True, help="GitHub repo in owner/name format."
    )
    parser.add_argument(
        "--pr-number", required=True, type=int, help="Pull request number."
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GITHUB_TOKEN", ""),
        help="GitHub token (defaults to GITHUB_TOKEN).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser(
        "pr-summary",
        help="Summarize traceability state for a pull request.",
    )
    summary_parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Append the summary to GITHUB_STEP_SUMMARY when available.",
    )

    absorption_parser = subparsers.add_parser(
        "master-absorption",
        help="Verify that the merged PR is absorbed in master.",
    )
    absorption_parser.add_argument(
        "--master-ref",
        default="origin/master",
        help="Ref used as the canonical absorption target.",
    )
    absorption_parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip `git fetch origin` before checking absorption.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")

    trace = fetch_pull_request_trace(token, repo=args.repo, pr_number=args.pr_number)

    if args.command == "pr-summary":
        lines = _format_pr_summary(trace)
        if args.write_summary:
            _write_summary(lines)
        print("\n".join(lines))
        return 0

    absorbed_sha = verify_absorption_in_master(
        trace,
        master_ref=args.master_ref,
        fetch_remote=not args.no_fetch,
    )
    lines = [
        "## PR Master Absorption",
        f"- PR: `#{trace.number}`",
        f"- URL: {trace.url}",
        f"- Verified commit: `{absorbed_sha}`",
        f"- Target ref: `{args.master_ref}`",
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TraceabilityError as exc:
        print(f"[pr-traceability] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
