#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT / "migrations" / "versions"


def _normalize_down_revisions(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple):
        revisions: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise SystemExit("down_revision contém valor não suportado.")
            revisions.append(item)
        return tuple(revisions)
    raise SystemExit("down_revision com formato não suportado.")


def _read_migration_metadata(path: Path) -> tuple[str, tuple[str, ...]]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    revision: str | None = None
    down_revisions: tuple[str, ...] = ()
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "revision":
                revision_value = ast.literal_eval(node.value)
                if not isinstance(revision_value, str):
                    raise SystemExit(f"revision inválido em {path}")
                revision = revision_value
            if target.id == "down_revision":
                down_revisions = _normalize_down_revisions(ast.literal_eval(node.value))
    if revision is None:
        raise SystemExit(f"revision não encontrado em {path}")
    return revision, down_revisions


def main() -> int:
    revisions: set[str] = set()
    referenced: set[str] = set()
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        revision, down_revisions = _read_migration_metadata(path)
        revisions.add(revision)
        referenced.update(down_revisions)
    heads = sorted(revisions - referenced)
    if len(heads) != 1:
        raise SystemExit(
            f"[alembic-single-head-check] expected 1 head, found {len(heads)}: {heads}"
        )
    print(f"[alembic-single-head-check] ok: single head {heads[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
