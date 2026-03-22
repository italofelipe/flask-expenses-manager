from __future__ import annotations

import json
from pathlib import Path

from scripts import sonar_enforce_ci


def test_build_selector_query_prefers_pull_request() -> None:
    selector = sonar_enforce_ci.build_selector_query(
        pull_request="123",
        branch="feature/test",
    )
    assert selector == "&pullRequest=123"


def test_build_report_collects_policy_errors() -> None:
    report = sonar_enforce_ci.build_report(
        quality_gate_payload={"projectStatus": {"status": "OK"}},
        measures_payload={
            "component": {
                "measures": [
                    {"metric": "security_rating", "value": "1.0"},
                    {"metric": "reliability_rating", "value": "1.0"},
                    {"metric": "sqale_rating", "value": "1.0"},
                    {"metric": "bugs", "value": "0"},
                    {"metric": "vulnerabilities", "value": "0"},
                    {"metric": "code_smells", "value": "9"},
                    {"metric": "coverage", "value": "89.7"},
                    {"metric": "duplicated_lines_density", "value": "1.0"},
                ]
            }
        },
        critical_blocker_payload={"total": 9},
        bug_vuln_payload={"total": 0},
        selector_query="&branch=master",
    )

    assert report["quality_gate_status"] == "OK"
    assert report["critical_blocker_open"] == 9
    assert report["errors"] == ["There are 9 open critical/blocker issues."]


def test_format_summary_includes_failure_reasons() -> None:
    summary = sonar_enforce_ci.format_summary(
        {
            "quality_gate_status": "OK",
            "security_rating": "1.0",
            "reliability_rating": "1.0",
            "maintainability_rating": "1.0",
            "bugs": 0,
            "vulnerabilities": 0,
            "code_smells": 9,
            "critical_blocker_open": 9,
            "bug_vuln_open": 0,
            "coverage": "89.7",
            "duplication": "1.0",
            "errors": ["There are 9 open critical/blocker issues."],
        }
    )

    assert "### Sonar Policy Report" in summary
    assert "#### Failure reasons" in summary
    assert "- There are 9 open critical/blocker issues." in summary


def test_write_json_report_persists_payload(tmp_path: Path) -> None:
    target = tmp_path / "reports" / "sonar-policy.json"
    payload = {"quality_gate_status": "OK", "errors": []}

    sonar_enforce_ci.write_json_report(str(target), payload)

    assert json.loads(target.read_text(encoding="utf-8")) == payload
