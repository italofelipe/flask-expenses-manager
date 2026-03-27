from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _load_module():
    import importlib.util

    module_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "pr_traceability_check.py"
    )
    spec = importlib.util.spec_from_file_location("pr_traceability_check", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_pull_request_flags_release_and_stacked() -> None:
    module = _load_module()

    trace = module._extract_pull_request(
        {
            "repository": {
                "pullRequest": {
                    "number": 715,
                    "title": "chore(master): release 1.6.0",
                    "url": "https://example.test/pr/715",
                    "state": "OPEN",
                    "isDraft": False,
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "baseRefName": "master",
                    "headRefName": (
                        "release-please--branches--master--components--auraxis-api"
                    ),
                    "headRefOid": "abc123",
                    "mergedAt": None,
                    "mergeCommit": None,
                }
            }
        },
        repo="italofelipe/auraxis-api",
        pr_number=715,
    )

    assert trace.is_release_pr is True
    assert trace.is_stacked_pr is False
    assert trace.absorption_commit_oid == "abc123"


def test_extract_pull_request_detects_stacked_pr() -> None:
    module = _load_module()

    trace = module._extract_pull_request(
        {
            "repository": {
                "pullRequest": {
                    "number": 718,
                    "title": "feat(j2): bank import preview",
                    "url": "https://example.test/pr/718",
                    "state": "MERGED",
                    "isDraft": False,
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "UNKNOWN",
                    "baseRefName": "feat/api-j2-parsers",
                    "headRefName": "feat/api-j2-preview",
                    "headRefOid": "head-sha",
                    "mergedAt": "2026-03-26T00:00:00Z",
                    "mergeCommit": {"oid": "merge-sha"},
                }
            }
        },
        repo="italofelipe/auraxis-api",
        pr_number=718,
    )

    assert trace.is_release_pr is False
    assert trace.is_stacked_pr is True
    assert trace.absorption_commit_oid == "merge-sha"


def test_format_pr_summary_mentions_release_and_stacked_policy() -> None:
    module = _load_module()
    trace = module.PullRequestTrace(
        number=720,
        title="feat(j2): complete bank statement import flow",
        url="https://example.test/pr/720",
        state="OPEN",
        is_draft=False,
        mergeable="MERGEABLE",
        merge_state_status="BLOCKED",
        base_ref_name="feat/api-j2-parsers",
        head_ref_name="feat/api-j2-complete",
        head_ref_oid="head-sha",
        merged_at=None,
        merge_commit_oid=None,
    )

    lines = module._format_pr_summary(trace)

    assert any("Stacked PR: `yes`" in line for line in lines)
    assert any("Policy: confirm absorption in `master`" in line for line in lines)


def test_verify_absorption_in_master_requires_merged_pr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    trace = module.PullRequestTrace(
        number=720,
        title="feat(j2): complete bank statement import flow",
        url="https://example.test/pr/720",
        state="OPEN",
        is_draft=False,
        mergeable="MERGEABLE",
        merge_state_status="BLOCKED",
        base_ref_name="master",
        head_ref_name="feat/api-j2-complete",
        head_ref_oid="head-sha",
        merged_at=None,
        merge_commit_oid=None,
    )

    with pytest.raises(module.TraceabilityError, match="not merged"):
        module.verify_absorption_in_master(
            trace,
            master_ref="origin/master",
            fetch_remote=False,
        )


def test_verify_absorption_in_master_uses_merge_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    trace = module.PullRequestTrace(
        number=720,
        title="feat(j2): complete bank statement import flow",
        url="https://example.test/pr/720",
        state="MERGED",
        is_draft=False,
        mergeable="MERGEABLE",
        merge_state_status="MERGED",
        base_ref_name="master",
        head_ref_name="feat/api-j2-complete",
        head_ref_oid="head-sha",
        merged_at="2026-03-26T00:00:00Z",
        merge_commit_oid="merge-sha",
    )

    captured: list[list[str]] = []

    def fake_run(args, check, capture_output, text):
        captured.append(args)

        class Result:
            returncode = 0
            stderr = ""

        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    absorbed = module.verify_absorption_in_master(
        trace,
        master_ref="origin/master",
        fetch_remote=False,
    )

    assert absorbed == "merge-sha"
    assert captured == [
        ["git", "merge-base", "--is-ancestor", "merge-sha", "origin/master"]
    ]
