#!/usr/bin/env python3
"""CI gate: entitlement coverage check (issue #1057).

Enforces bidirectional consistency between docs/entitlement-matrix.md
and the actual `@require_entitlement(...)` / `has_entitlement(...)` guards
in the source code.

Rules
-----
1. Every `@require_entitlement("X")` decorator found in app/controllers/**
   must have a corresponding entry in DOCUMENTED_REST_GUARDS below.
2. Every entry in DOCUMENTED_REST_GUARDS must exist in the source.
3. Every `_require_advanced_simulations` / `has_entitlement(...)` guard
   found in app/graphql/** must have a matching entry in
   DOCUMENTED_GRAPHQL_GUARDS below.
4. Every entry in DOCUMENTED_GRAPHQL_GUARDS must exist in the source.

Usage
-----
    python3 scripts/entitlement_coverage_check.py

Exit code 0 = all guards documented; exit code 1 = drift detected.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLLERS_DIR = ROOT / "app" / "controllers"
GRAPHQL_DIR = ROOT / "app" / "graphql"

# ---------------------------------------------------------------------------
# Canonical matrix (mirrors docs/entitlement-matrix.md)
# Each entry: (relative_path_from_root, feature_key)
# ---------------------------------------------------------------------------

DOCUMENTED_REST_GUARDS: set[tuple[str, str]] = {
    ("app/controllers/transaction/export_resource.py", "export_pdf"),
    (
        "app/controllers/simulation/installment_vs_cash_resources.py",
        "advanced_simulations",
    ),
}

# For GraphQL we track by file + count of `has_entitlement(` call sites.
# Internal _require_* helpers are wrappers and not counted separately.
DOCUMENTED_GRAPHQL_GUARDS: dict[str, int] = {
    # 1 has_entitlement() call inside _require_advanced_simulations helper
    "app/graphql/mutations/simulation.py": 1,
}

# Pattern: @require_entitlement("feature_key") in controllers
_REST_PATTERN = re.compile(r'@require_entitlement\(\s*["\']([^"\']+)["\']\s*\)')

# Only count direct has_entitlement() calls — these are the actual guard sites.
# Internal _require_* helper functions are wrappers, not additional guard sites.
_GQL_HAS_ENTITLEMENT = re.compile(r"has_entitlement\(")

# Artifact files produced by macOS AI copy (e.g. "foo 2.py") are ignored.
_ARTIFACT_SUFFIX = re.compile(r" \d+\.py$")


def _find_rest_guards() -> dict[str, set[str]]:
    """Return {relative_path: {feature_key, ...}} for all controller files.

    Artifact files (e.g. "foo 2.py") produced by macOS AI copy-paste are skipped.
    """
    found: dict[str, set[str]] = {}
    for path in CONTROLLERS_DIR.rglob("*.py"):
        if _ARTIFACT_SUFFIX.search(path.name):
            continue
        content = path.read_text(encoding="utf-8")
        matches = _REST_PATTERN.findall(content)
        if matches:
            rel = str(path.relative_to(ROOT))
            found[rel] = set(matches)
    return found


def _find_graphql_guards() -> dict[str, int]:
    """Return {relative_path: has_entitlement_call_count} for all graphql files.

    Only direct `has_entitlement(` call sites are counted — internal helper
    functions (`_require_*`) are wrappers, not additional guard sites.
    """
    found: dict[str, int] = {}
    for path in GRAPHQL_DIR.rglob("*.py"):
        if _ARTIFACT_SUFFIX.search(path.name):
            continue
        content = path.read_text(encoding="utf-8")
        count = len(_GQL_HAS_ENTITLEMENT.findall(content))
        if count:
            rel = str(path.relative_to(ROOT))
            found[rel] = count
    return found


def main() -> int:  # noqa: C901
    errors: list[str] = []

    # ── REST controllers ──────────────────────────────────────────────────────
    found_rest = _find_rest_guards()

    # Build what the code declares
    found_rest_pairs: set[tuple[str, str]] = set()
    for rel, keys in found_rest.items():
        for key in keys:
            found_rest_pairs.add((rel, key))

    # Rule 1: in code but not in matrix
    undocumented = found_rest_pairs - DOCUMENTED_REST_GUARDS
    for rel, key in sorted(undocumented):
        errors.append(
            f"[entitlement-matrix] UNDOCUMENTED guard in {rel}: "
            f'@require_entitlement("{key}") — add to docs/entitlement-matrix.md '
            f"and DOCUMENTED_REST_GUARDS in this script"
        )

    # Rule 2: in matrix but not in code
    missing = DOCUMENTED_REST_GUARDS - found_rest_pairs
    for rel, key in sorted(missing):
        errors.append(
            f"[entitlement-matrix] STALE matrix entry {rel}@{key} — "
            f"guard no longer found in source; remove from matrix and this script"
        )

    # ── GraphQL mutations ─────────────────────────────────────────────────────
    found_gql = _find_graphql_guards()

    # Rule 3: in code but not in matrix
    for rel, count in sorted(found_gql.items()):
        expected = DOCUMENTED_GRAPHQL_GUARDS.get(rel)
        if expected is None:
            errors.append(
                f"[entitlement-matrix] UNDOCUMENTED graphql guard(s) in {rel} "
                f"({count} found) — add to docs/entitlement-matrix.md and "
                f"DOCUMENTED_GRAPHQL_GUARDS in this script"
            )
        elif count != expected:
            errors.append(
                f"[entitlement-matrix] Guard count mismatch in {rel}: "
                f"expected {expected}, found {count} — update DOCUMENTED_GRAPHQL_GUARDS"
            )

    # Rule 4: in matrix but not in code
    for rel, _expected in sorted(DOCUMENTED_GRAPHQL_GUARDS.items()):
        if rel not in found_gql:
            errors.append(
                f"[entitlement-matrix] STALE graphql matrix entry {rel} — "
                f"no guards found in source; remove from matrix and this script"
            )

    if errors:
        for msg in errors:
            print(msg, file=sys.stderr)
        return 1

    total_rest = sum(len(v) for v in found_rest.values())
    total_gql = sum(found_gql.values())
    print(
        f"[entitlement-matrix] ok: {total_rest} REST guard(s), "
        f"{total_gql} GraphQL guard(s) — all documented"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
