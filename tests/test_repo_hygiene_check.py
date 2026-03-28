from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "repo_hygiene_check.py"
    )
    spec = importlib.util.spec_from_file_location("repo_hygiene_check", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_find_hygiene_violations_detects_duplicate_suffix_file(tmp_path: Path) -> None:
    module = _load_module()
    duplicate = tmp_path / "app" / "services" / "bank_import_service 2.py"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_text("print('hi')\n", encoding="utf-8")

    violations = module.find_hygiene_violations(tmp_path)

    assert [item.relative_path for item in violations] == [
        "app/services/bank_import_service 2.py"
    ]


def test_find_hygiene_violations_ignores_safe_directories(tmp_path: Path) -> None:
    module = _load_module()
    ignored = tmp_path / "_worktrees" / "sandbox" / "bank_import_service 2.py"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("print('hi')\n", encoding="utf-8")

    violations = module.find_hygiene_violations(tmp_path)

    assert violations == []


def test_find_hygiene_violations_ignores_regular_numbered_names(tmp_path: Path) -> None:
    module = _load_module()
    healthy = tmp_path / "scripts" / "api18_step_2.py"
    healthy.parent.mkdir(parents=True)
    healthy.write_text("print('ok')\n", encoding="utf-8")

    violations = module.find_hygiene_violations(tmp_path)

    assert violations == []
