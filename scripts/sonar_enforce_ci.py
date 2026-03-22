from __future__ import annotations

import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, cast

DEFAULT_SONAR_HOST_URL = "https://sonarcloud.io"


def normalize_env_var(value: str) -> str:
    return value.strip()


def urlencode(raw: str) -> str:
    return urllib.parse.quote(raw, safe="")


def is_a(value: str) -> bool:
    normalized = value.strip().upper()
    if normalized == "A":
        return True
    try:
        return float(normalized) <= 1.0
    except ValueError:
        return False


def build_selector_query(*, pull_request: str, branch: str) -> str:
    if pull_request:
        return f"&pullRequest={urlencode(pull_request)}"
    if branch:
        return f"&branch={urlencode(branch)}"
    return ""


def sonar_get(
    *,
    endpoint: str,
    sonar_host_url: str,
    sonar_token: str,
    selector_query: str,
) -> dict[str, Any]:
    url = f"{sonar_host_url}{endpoint}{selector_query}"
    token_bytes = f"{sonar_token}:".encode("utf-8")
    auth_header = "Basic " + base64.b64encode(token_bytes).decode("ascii")
    request = urllib.request.Request(url)
    request.add_header("Authorization", auth_header)
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(
                f"Sonar API request failed ({response.status}) for: {endpoint}"
            )
        payload = json.loads(response.read().decode("utf-8"))
        return cast(dict[str, Any], payload)


def build_report(
    *,
    quality_gate_payload: dict[str, Any],
    measures_payload: dict[str, Any],
    critical_blocker_payload: dict[str, Any],
    bug_vuln_payload: dict[str, Any],
    selector_query: str,
) -> dict[str, Any]:
    quality_gate_status = quality_gate_payload.get("projectStatus", {}).get(
        "status", "UNKNOWN"
    )
    measures = measures_payload.get("component", {}).get("measures", [])
    metrics = {item["metric"]: item.get("value", "") for item in measures}

    report = {
        "selector_query": selector_query or "",
        "quality_gate_status": quality_gate_status,
        "security_rating": metrics.get("security_rating", ""),
        "reliability_rating": metrics.get("reliability_rating", ""),
        "maintainability_rating": metrics.get("sqale_rating", ""),
        "bugs": int(float(metrics.get("bugs", "0") or "0")),
        "vulnerabilities": int(float(metrics.get("vulnerabilities", "0") or "0")),
        "code_smells": int(float(metrics.get("code_smells", "0") or "0")),
        "coverage": metrics.get("coverage", "N/A"),
        "duplication": metrics.get("duplicated_lines_density", "N/A"),
        "critical_blocker_open": int(critical_blocker_payload.get("total", 0)),
        "bug_vuln_open": int(bug_vuln_payload.get("total", 0)),
    }
    report["errors"] = build_errors(report)
    return report


def build_errors(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if report["quality_gate_status"] != "OK":
        errors.append(
            f"Quality Gate status is {report['quality_gate_status']} (expected OK)."
        )
    if not is_a(report["security_rating"]):
        errors.append(
            f"Security rating must be A (current: {report['security_rating']})."
        )
    if not is_a(report["reliability_rating"]):
        errors.append(
            f"Reliability rating must be A (current: {report['reliability_rating']})."
        )
    if not is_a(report["maintainability_rating"]):
        errors.append(
            "Maintainability rating must be A "
            f"(current: {report['maintainability_rating']})."
        )
    if report["critical_blocker_open"] > 0:
        errors.append(
            f"There are {report['critical_blocker_open']} open critical/blocker issues."
        )
    if report["bugs"] > 0:
        errors.append(f"There are {report['bugs']} open bugs.")
    if report["vulnerabilities"] > 0:
        errors.append(f"There are {report['vulnerabilities']} open vulnerabilities.")
    if report["bug_vuln_open"] > 0:
        errors.append(
            "There are "
            f"{report['bug_vuln_open']} open BUG/VULNERABILITY issues in issues API."
        )

    return errors


def format_summary(report: dict[str, Any]) -> str:
    lines = [
        "### Sonar Policy Report",
        "",
        f"- Quality Gate: `{report['quality_gate_status']}`",
        f"- Security Rating: `{report['security_rating']}`",
        f"- Reliability Rating: `{report['reliability_rating']}`",
        f"- Maintainability Rating: `{report['maintainability_rating']}`",
        f"- Open Bugs (all severities): `{report['bugs']}`",
        f"- Open Vulnerabilities (all severities): `{report['vulnerabilities']}`",
        f"- Open Code Smells: `{report['code_smells']}`",
        f"- Open Critical/Blocker issues: `{report['critical_blocker_open']}`",
        f"- Open BUG/VULNERABILITY issues: `{report['bug_vuln_open']}`",
        f"- Coverage: `{report['coverage']}`",
        f"- Duplicated Lines Density: `{report['duplication']}`",
    ]

    if report["errors"]:
        lines.extend(["", "#### Failure reasons", ""])
        lines.extend(f"- {error}" for error in report["errors"])

    return "\n".join(lines)


def write_summary(summary: str) -> None:
    print(summary)
    github_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary_path:
        with open(github_summary_path, "a", encoding="utf-8") as fp:
            fp.write(summary + "\n")


def write_json_report(path: str, report: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    sonar_host_url = normalize_env_var(
        os.environ.get("SONAR_HOST_URL", DEFAULT_SONAR_HOST_URL)
    )
    sonar_token = normalize_env_var(os.environ.get("SONAR_TOKEN", ""))
    sonar_project_key = normalize_env_var(os.environ.get("SONAR_PROJECT_KEY", ""))
    sonar_branch = normalize_env_var(os.environ.get("SONAR_BRANCH", ""))
    sonar_pull_request = normalize_env_var(os.environ.get("SONAR_PULL_REQUEST", ""))
    report_path = normalize_env_var(os.environ.get("SONAR_POLICY_REPORT_PATH", ""))

    if not sonar_token or not sonar_project_key:
        print(
            "Missing required environment variable: SONAR_TOKEN/SONAR_PROJECT_KEY",
            file=sys.stderr,
        )
        return 1

    selector_query = build_selector_query(
        pull_request=sonar_pull_request,
        branch=sonar_branch,
    )

    quality_gate_payload = sonar_get(
        endpoint=f"/api/qualitygates/project_status?projectKey={sonar_project_key}",
        sonar_host_url=sonar_host_url,
        sonar_token=sonar_token,
        selector_query=selector_query,
    )
    measures_payload = sonar_get(
        endpoint=(
            "/api/measures/component?"
            f"component={sonar_project_key}"
            "&metricKeys=security_rating,reliability_rating,sqale_rating,"
            "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density"
        ),
        sonar_host_url=sonar_host_url,
        sonar_token=sonar_token,
        selector_query=selector_query,
    )
    critical_blocker_payload = sonar_get(
        endpoint=(
            "/api/issues/search?"
            f"componentKeys={sonar_project_key}&severities=BLOCKER,CRITICAL"
            "&resolved=false&ps=1"
        ),
        sonar_host_url=sonar_host_url,
        sonar_token=sonar_token,
        selector_query=selector_query,
    )
    bug_vuln_payload = sonar_get(
        endpoint=(
            "/api/issues/search?"
            f"componentKeys={sonar_project_key}&types=BUG,VULNERABILITY"
            "&resolved=false&ps=1"
        ),
        sonar_host_url=sonar_host_url,
        sonar_token=sonar_token,
        selector_query=selector_query,
    )

    report = build_report(
        quality_gate_payload=quality_gate_payload,
        measures_payload=measures_payload,
        critical_blocker_payload=critical_blocker_payload,
        bug_vuln_payload=bug_vuln_payload,
        selector_query=selector_query,
    )
    summary = format_summary(report)
    write_summary(summary)
    if report_path:
        write_json_report(report_path, report)

    if report["errors"]:
        print("\nSonar policy check failed:", file=sys.stderr)
        for error in report["errors"]:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("\nSonar policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
