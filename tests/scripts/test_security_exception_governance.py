from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "security_exception_governance.py"
    )
    spec = importlib.util.spec_from_file_location(
        "security_exception_governance", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_security_exceptions_requires_metadata(tmp_path: Path) -> None:
    module = _load_module()
    config_path = tmp_path / "exceptions.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "exceptions": [
                    {
                        "id": "GHSA-example",
                        "tools": ["pip-audit"],
                        "owner": "platform-security",
                        "reviewed_at": "2026-03-27",
                        "justification": "Awaiting upstream fix.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exceptions = module.load_security_exceptions(config_path)

    assert [item.id for item in exceptions] == ["GHSA-example"]
    assert exceptions[0].tools == ("pip-audit",)


def test_build_pip_audit_args_emits_ignore_flags(tmp_path: Path) -> None:
    module = _load_module()
    config_path = tmp_path / "exceptions.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "exceptions": [
                    {
                        "id": "GHSA-a",
                        "tools": ["pip-audit", "osv-scanner"],
                        "owner": "platform-security",
                        "reviewed_at": "2026-03-27",
                        "justification": "Awaiting upstream fix.",
                    },
                    {
                        "id": "GHSA-b",
                        "tools": ["osv-scanner"],
                        "owner": "platform-security",
                        "reviewed_at": "2026-03-27",
                        "justification": "Awaiting upstream fix.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    exceptions = module.load_security_exceptions(config_path)

    assert module.build_pip_audit_args(exceptions) == ["--ignore-vuln", "GHSA-a"]
    assert module.build_osv_allowlist(exceptions) == "GHSA-a,GHSA-b"


def test_load_security_exceptions_rejects_duplicate_ids(tmp_path: Path) -> None:
    module = _load_module()
    config_path = tmp_path / "exceptions.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "exceptions": [
                    {
                        "id": "GHSA-a",
                        "tools": ["pip-audit"],
                        "owner": "platform-security",
                        "reviewed_at": "2026-03-27",
                        "justification": "Awaiting upstream fix.",
                    },
                    {
                        "id": "GHSA-a",
                        "tools": ["osv-scanner"],
                        "owner": "platform-security",
                        "reviewed_at": "2026-03-27",
                        "justification": "Awaiting upstream fix.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(module.SecurityExceptionGovernanceError):
        module.load_security_exceptions(config_path)
