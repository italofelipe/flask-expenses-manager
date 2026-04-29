#!/usr/bin/env python3
"""Verify the backend tools registry mirrors the canonical app catalog.

The canonical list of `tool_id` values lives in
``auraxis-app/features/tools/services/tools-catalog.ts``. The backend
registry at ``app/simulations/tools_registry.py`` must mirror it exactly
so that ``POST /simulations`` accepts every tool the app catalog declares
and rejects unknown ones (DEC-196 / #1128).

This script is intended to be run in CI. It exits 0 when registries match
and 1 with a diff when they drift.

Resolution order for the app catalog (first existing path wins):

1. ``$AURAXIS_APP_CATALOG_PATH`` — explicit override (CI/local).
2. ``../auraxis-app/features/tools/services/tools-catalog.ts`` — sibling
   checkout next to ``auraxis-api`` (legacy layout).
3. ``../../repos/auraxis-app/features/tools/services/tools-catalog.ts``
    — platform submodule layout (current canonical structure).

When none exists the check is skipped with a clear message rather than
failing CI on environments where the app source is not available.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def _candidate_paths() -> list[Path]:
    here = Path(__file__).resolve()
    repo_root = here.parent.parent
    candidates: list[Path] = []
    override = os.environ.get("AURAXIS_APP_CATALOG_PATH")
    if override:
        candidates.append(Path(override).expanduser().resolve())
    candidates.append(
        repo_root.parent / "auraxis-app/features/tools/services/tools-catalog.ts"
    )
    candidates.append(
        repo_root.parent.parent
        / "repos/auraxis-app/features/tools/services/tools-catalog.ts"
    )
    return candidates


def _read_app_catalog() -> tuple[Path, str] | None:
    for candidate in _candidate_paths():
        if candidate.exists():
            return candidate, candidate.read_text(encoding="utf-8")
    return None


_TOOL_ID_PATTERN = re.compile(r'\[\s*"([a-z][a-z0-9-]*)"')


def _extract_app_tool_ids(source: str) -> set[str]:
    return set(_TOOL_ID_PATTERN.findall(source))


_BACKEND_TOOL_PATTERN = re.compile(r'^\s*"([a-z][a-z0-9-]*)"\s*,\s*$', re.M)
_LEGACY_TOOL_PATTERN = re.compile(
    r"LEGACY_TOOL_IDS\s*:\s*frozenset\[str\]\s*=\s*frozenset\(\{(.*?)\}\)",
    re.S,
)
_QUOTED_PATTERN = re.compile(r'"([a-z][a-z0-9_-]*)"')


def _load_backend_registry() -> tuple[set[str], set[str]]:
    """Parse the registry source as text to avoid importing the Flask app.

    Returns ``(canonical, legacy)`` so the caller can exclude legacy ids from
    the parity diff while still ensuring they are present in the file.
    """
    here = Path(__file__).resolve()
    registry_path = here.parent.parent / "app/simulations/tools_registry.py"
    source = registry_path.read_text(encoding="utf-8")
    # Restrict to the canonical frozenset literal block to avoid pulling
    # unrelated quoted strings (e.g., docstring examples).
    start = source.find("TOOLS_REGISTRY")
    paren = source.find("frozenset(", start)
    # The frozenset literal closes with "})" (set literal followed by call
    # close). Searching for ")" alone trips on parenthesised text inside
    # the comment block.
    end = source.find("})", paren)
    if start == -1 or paren == -1 or end == -1:
        raise RuntimeError(
            "Could not locate TOOLS_REGISTRY frozenset(...) literal — "
            "registry layout changed; update this parser."
        )
    canonical_block = source[paren : end + 2]
    canonical = set(_BACKEND_TOOL_PATTERN.findall(canonical_block))
    legacy_match = _LEGACY_TOOL_PATTERN.search(source)
    legacy = (
        set(_QUOTED_PATTERN.findall(legacy_match.group(1))) if legacy_match else set()
    )
    return canonical - legacy, legacy


def main() -> int:
    found = _read_app_catalog()
    if found is None:
        print(
            "tools-registry-parity: SKIPPED — auraxis-app catalog not found "
            "(set AURAXIS_APP_CATALOG_PATH to enforce locally).",
            file=sys.stderr,
        )
        return 0
    catalog_path, source = found
    app_ids = _extract_app_tool_ids(source)
    canonical_ids, legacy_ids = _load_backend_registry()

    missing_in_backend = sorted(app_ids - canonical_ids)
    missing_in_app = sorted(canonical_ids - app_ids)

    if not missing_in_backend and not missing_in_app:
        legacy_note = f" + {len(legacy_ids)} legacy" if legacy_ids else ""
        print(
            f"tools-registry-parity: OK "
            f"({len(canonical_ids)} canonical{legacy_note}) "
            f"[catalog: {catalog_path}]"
        )
        return 0

    print("tools-registry-parity: FAIL — drift detected", file=sys.stderr)
    print(f"  catalog: {catalog_path}", file=sys.stderr)
    if missing_in_backend:
        print(
            f"  missing in backend registry ({len(missing_in_backend)}):",
            file=sys.stderr,
        )
        for tid in missing_in_backend:
            print(f"    + {tid}", file=sys.stderr)
    if missing_in_app:
        print(
            f"  missing in app catalog ({len(missing_in_app)}):",
            file=sys.stderr,
        )
        for tid in missing_in_app:
            print(f"    - {tid}", file=sys.stderr)
    print(
        "Update both files in the same PR to re-establish parity.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
