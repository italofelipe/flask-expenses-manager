#!/usr/bin/env python3
"""Audit and sync GitHub repository rulesets for branch governance.

Usage examples:
  python scripts/github_ruleset_manager.py --mode audit --owner ORG --repo REPO
  python scripts/github_ruleset_manager.py --mode sync --owner ORG --repo REPO
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API_VERSION = "2022-11-28"
BASE_URL = "https://api.github.com"


class RulesetError(RuntimeError):
    """Raised when ruleset audit/sync cannot be completed safely."""


@dataclass
class GitHubClient:
    token: str

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        url = f"{BASE_URL}{path}"
        data = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "auraxis-ruleset-manager",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8").strip()
                if not body:
                    return {}
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RulesetError(
                f"GitHub API request failed: {method} {path} -> {exc.code}\n{body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RulesetError(f"GitHub API network error: {exc}") from exc

    def list_rulesets(self, owner: str, repo: str) -> list[dict[str, Any]]:
        result = self._request("GET", f"/repos/{owner}/{repo}/rulesets")
        if not isinstance(result, list):
            raise RulesetError("Unexpected response for list rulesets")
        return result

    def create_ruleset(
        self, owner: str, repo: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        result = self._request("POST", f"/repos/{owner}/{repo}/rulesets", payload)
        if not isinstance(result, dict):
            raise RulesetError("Unexpected response for create ruleset")
        return result

    def update_ruleset(
        self, owner: str, repo: str, ruleset_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        result = self._request(
            "PUT", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}", payload
        )
        if not isinstance(result, dict):
            raise RulesetError("Unexpected response for update ruleset")
        return result


def _load_config(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as exc:
        raise RulesetError(f"Config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RulesetError(f"Invalid JSON in config {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RulesetError("Ruleset config root must be an object")
    return data


def _normalize_status_check(check: Any) -> dict[str, Any] | None:
    if not isinstance(check, dict):
        return None
    context = check.get("context")
    if not isinstance(context, str) or not context:
        return None

    normalized_check: dict[str, Any] = {"context": context}
    integration_id = check.get("integration_id")
    if isinstance(integration_id, int):
        normalized_check["integration_id"] = integration_id
    return normalized_check


def _normalize_required_status_checks_rule(rule: dict[str, Any]) -> None:
    if rule.get("type") != "required_status_checks":
        return

    parameters = rule.get("parameters")
    if not isinstance(parameters, dict):
        return

    required = parameters.get("required_status_checks")
    if not isinstance(required, list):
        return

    cleaned_required: list[dict[str, Any]] = []
    for check in required:
        normalized_check = _normalize_status_check(check)
        if normalized_check is not None:
            cleaned_required.append(normalized_check)
    parameters["required_status_checks"] = cleaned_required


def _normalize_ruleset_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize payload to GitHub Rulesets API accepted shape."""
    normalized: dict[str, Any] = json.loads(json.dumps(payload))
    rules = normalized.get("rules")
    if not isinstance(rules, list):
        return normalized

    for rule in rules:
        if isinstance(rule, dict):
            _normalize_required_status_checks_rule(rule)
    return normalized


def _rules_by_type(rules: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for rule in rules:
        rule_type = rule.get("type")
        if isinstance(rule_type, str):
            mapping[rule_type] = rule
    return mapping


def _find_named_ruleset(
    rulesets: list[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    for ruleset in rulesets:
        if ruleset.get("name") == name:
            return ruleset
    return None


def _extract_status_check_contexts(rule: dict[str, Any]) -> set[str]:
    parameters = rule.get("parameters", {})
    required = parameters.get("required_status_checks", [])
    contexts: set[str] = set()
    if isinstance(required, list):
        for check in required:
            if isinstance(check, dict):
                context = check.get("context")
                if isinstance(context, str) and context:
                    contexts.add(context)
    return contexts


def audit_ruleset(current: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    issues: list[str] = []

    for key in ("target", "enforcement"):
        if current.get(key) != expected.get(key):
            expected_value = expected.get(key)
            current_value = current.get(key)
            issues.append(
                f"Mismatch for '{key}': "
                f"expected={expected_value!r} current={current_value!r}"
            )

    expected_conditions = expected.get("conditions", {})
    current_conditions = current.get("conditions", {})
    expected_include = (
        expected_conditions.get("ref_name", {}).get("include", [])
        if isinstance(expected_conditions, dict)
        else []
    )
    current_include = (
        current_conditions.get("ref_name", {}).get("include", [])
        if isinstance(current_conditions, dict)
        else []
    )
    if set(expected_include) != set(current_include):
        issues.append(
            "Ref include mismatch: "
            f"expected={sorted(expected_include)!r} current={sorted(current_include)!r}"
        )

    expected_rules = _rules_by_type(expected.get("rules", []))
    current_rules = _rules_by_type(current.get("rules", []))

    missing_rule_types = sorted(set(expected_rules) - set(current_rules))
    if missing_rule_types:
        issues.append(f"Missing required rule types: {missing_rule_types}")

    expected_pr = expected_rules.get("pull_request", {}).get("parameters", {})
    current_pr = current_rules.get("pull_request", {}).get("parameters", {})
    if isinstance(expected_pr, dict) and isinstance(current_pr, dict):
        for key, value in expected_pr.items():
            if current_pr.get(key) != value:
                current_value = current_pr.get(key)
                issues.append(
                    f"Pull request rule mismatch for '{key}': "
                    f"expected={value!r} current={current_value!r}"
                )

    expected_checks = _extract_status_check_contexts(
        expected_rules.get("required_status_checks", {})
    )
    current_checks = _extract_status_check_contexts(
        current_rules.get("required_status_checks", {})
    )
    missing_checks = sorted(expected_checks - current_checks)
    if missing_checks:
        issues.append(f"Missing required status checks: {missing_checks}")

    strict_expected = (
        expected_rules.get("required_status_checks", {})
        .get("parameters", {})
        .get("strict_required_status_checks_policy")
    )
    strict_current = (
        current_rules.get("required_status_checks", {})
        .get("parameters", {})
        .get("strict_required_status_checks_policy")
    )
    if strict_expected != strict_current:
        issues.append(
            "Mismatch for strict status checks policy: "
            f"expected={strict_expected!r} current={strict_current!r}"
        )

    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage GitHub ruleset for master governance."
    )
    parser.add_argument("--owner", required=True, help="Repository owner (org/user)")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument(
        "--config",
        default="config/github_master_ruleset.json",
        help="Path to desired ruleset JSON config",
    )
    parser.add_argument(
        "--token-env",
        default="TOKEN_GITHUB_ADMIN",
        help="Environment variable containing GitHub admin token",
    )
    parser.add_argument(
        "--mode",
        choices=("audit", "sync"),
        default="audit",
        help="audit: fail on drift; sync: create/update to desired state",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv(args.token_env, "").strip()
    if not token and args.token_env == "TOKEN_GITHUB_ADMIN":
        # Backward-compatible fallback for previous secret naming.
        token = os.getenv("GITHUB_ADMIN_TOKEN", "").strip()
    if not token:
        raise RulesetError(
            f"Missing token in environment variable '{args.token_env}'. "
            "Use a GitHub token with repository administration permissions."
        )

    config = _normalize_ruleset_payload(_load_config(Path(args.config)))
    ruleset_name = config.get("name")
    if not isinstance(ruleset_name, str) or not ruleset_name:
        raise RulesetError("Ruleset config must define a non-empty 'name'")

    client = GitHubClient(token=token)
    rulesets = client.list_rulesets(args.owner, args.repo)
    current = _find_named_ruleset(rulesets, ruleset_name)

    if args.mode == "audit":
        if current is None:
            raise RulesetError(
                f"Ruleset '{ruleset_name}' not found in {args.owner}/{args.repo}"
            )
        issues = audit_ruleset(current, config)
        if issues:
            message = "\n- ".join(["Ruleset drift detected:"] + issues)
            raise RulesetError(message)
        print(f"Ruleset '{ruleset_name}' is compliant.")
        return 0

    if current is None:
        created = client.create_ruleset(args.owner, args.repo, config)
        print(
            "Created ruleset "
            f"'{ruleset_name}' (id={created.get('id')}) for {args.owner}/{args.repo}."
        )
        return 0

    ruleset_id = current.get("id")
    if not isinstance(ruleset_id, int):
        raise RulesetError(f"Invalid ruleset id for '{ruleset_name}': {ruleset_id!r}")

    updated = client.update_ruleset(args.owner, args.repo, ruleset_id, config)
    print(
        "Updated ruleset "
        f"'{ruleset_name}' (id={updated.get('id')}) for {args.owner}/{args.repo}."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RulesetError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2)
