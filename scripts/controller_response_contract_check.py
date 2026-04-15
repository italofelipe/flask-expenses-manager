#!/usr/bin/env python3
"""CI gate: enforce response_contract usage across REST controllers.

Detects controller files that use `jsonify` directly without going through
app.controllers.response_contract or app.utils.response_builder, which are
the canonical wrappers for all JSON responses.

Motivation (issue #1047):
  - Inconsistent response formats when jsonify is used directly
  - Hard to add global fields (request_id, timestamp) in one place
  - Sonar CPD and code review friction

Allowed exceptions (intentional direct jsonify use):
  - app/utils/response_builder.py — the canonical jsonify wrapper itself
  - app/controllers/response_contract.py — the contract implementation
  - app/controllers/observability_controller.py — ops/metrics, non-user-facing
  - app/controllers/admin/feature_flags.py — admin ops, intentionally minimal
  - app/controllers/auth/error_handlers.py — webargs low-level error handler
    (abort() pattern requires raw make_response + jsonify)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLLERS_DIR = ROOT / "app/controllers"

# Files allowed to use jsonify directly (with documented reasons above).
ALLOWLIST: set[Path] = {
    ROOT / "app/utils/response_builder.py",
    ROOT / "app/controllers/response_contract.py",
    ROOT / "app/controllers/observability_controller.py",
    ROOT / "app/controllers/admin/feature_flags.py",
    ROOT / "app/controllers/auth/error_handlers.py",
}


def _imports_jsonify(tree: ast.Module) -> bool:
    """Return True if the module imports jsonify from flask."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "flask":
            continue
        if any(alias.name == "jsonify" for alias in node.names):
            return True
    return False


def _collect_controller_py_files() -> list[Path]:
    files: list[Path] = []
    for path in CONTROLLERS_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return sorted(files)


def main() -> int:
    violations: list[str] = []

    for path in _collect_controller_py_files():
        if path in ALLOWLIST:
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            print(f"  SKIP {path.relative_to(ROOT)}: syntax error — {exc}")
            continue

        if _imports_jsonify(tree):
            violations.append(
                f"  {path.relative_to(ROOT)}: imports jsonify directly. "
                f"Use app.controllers.response_contract or "
                f"app.utils.response_builder instead."
            )

    if violations:
        print(
            "controller-response-contract-check FAILED — direct jsonify detected:",
            file=sys.stderr,
        )
        for v in violations:
            print(v, file=sys.stderr)
        print(
            "\nMigrate to compat_success_response / compat_error_response from "
            "app.controllers.response_contract. To allow an exception, "
            "add the file to ALLOWLIST in this script with a reason comment.",
            file=sys.stderr,
        )
        return 1

    print(
        f"[controller-response-contract-check] ok — "
        f"{len(_collect_controller_py_files()) - len(ALLOWLIST)} "
        f"controller files audited, 0 direct jsonify usages."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
