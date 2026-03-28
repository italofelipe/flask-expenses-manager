#!/usr/bin/env python3
"""Guardrail for accidental duplicate-suffix files in the repository.

This catches common local artifact patterns such as ``foo 2.py`` before they
leak into commits, reviews, or automation flows.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
IGNORED_DIR_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "_worktrees",
        "node_modules",
        "repos",
    }
)
SUSPICIOUS_DUPLICATE_PATTERN = re.compile(r".+\s\d+\.[A-Za-z0-9]+$")


class RepoHygieneError(Exception):
    """Raised when the repository contains suspicious accidental duplicates."""


@dataclass(frozen=True)
class HygieneViolation:
    relative_path: str


def _iter_files(root_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        paths.append(path)
    return sorted(paths)


def find_hygiene_violations(root_dir: Path) -> list[HygieneViolation]:
    violations: list[HygieneViolation] = []
    for path in _iter_files(root_dir):
        if SUSPICIOUS_DUPLICATE_PATTERN.fullmatch(path.name) is None:
            continue
        violations.append(
            HygieneViolation(relative_path=str(path.relative_to(root_dir)))
        )
    return violations


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect suspicious duplicate-suffix files such as 'foo 2.py'."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT_DIR,
        help="Repository root to scan.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    root_dir = args.root.resolve()
    violations = find_hygiene_violations(root_dir)
    if not violations:
        print("[repo-hygiene-check] ok: no suspicious duplicate-suffix files found")
        return 0

    print(
        "[repo-hygiene-check] suspicious duplicate-suffix files detected:",
        file=sys.stderr,
    )
    for violation in violations:
        print(f"- {violation.relative_path}", file=sys.stderr)
    raise RepoHygieneError(
        "Remove or rename accidental duplicate files before committing."
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RepoHygieneError as exc:
        print(f"[repo-hygiene-check] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
