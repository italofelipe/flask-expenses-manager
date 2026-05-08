#!/usr/bin/env python3
"""INI-2: Lint de padrões proibidos em migrations Alembic.

Detecta anti-padrões que causam falhas silenciosas em SQLite mas explodem
contra PostgreSQL real no CI — especialmente CREATE TYPE sem idempotência
e APIs deprecated do SQLAlchemy 2.0.

Docs: docs/wiki/Post-Mortem-PR1174-Bootstrap-Migration.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Padrões proibidos
# ---------------------------------------------------------------------------

FORBIDDEN: list[tuple[str, re.Pattern[str], str]] = [
    (
        "CREATE TYPE sem guarda de idempotência",
        re.compile(r"op\.execute\([^)]*CREATE\s+TYPE\b", re.IGNORECASE | re.DOTALL),
        (
            "Use native_enum=False (preferido) ou verifique pg_type antes:\n"
            "  conn = op.get_context().connection\n"
            "  if not conn.execute(sa.text(\n"
            '      "SELECT 1 FROM pg_type WHERE typname = :n"),\n'
            '      {"n": "my_type"}).scalar():\n'
            '      conn.execute(sa.text("CREATE TYPE my_type AS ENUM (...)"))\n'
            "Ver: docs/wiki/Post-Mortem-PR1174-Bootstrap-Migration.md"
        ),
    ),
    (
        "op.get_bind() deprecated (SQLAlchemy 2.0)",
        re.compile(r"\bop\.get_bind\(\)", re.IGNORECASE),
        (
            "Substitua por: conn = op.get_context().connection\n"
            "Ou use op.execute() para DDL simples."
        ),
    ),
    (
        "postgresql.ENUM.create(op.get_bind()) — padrão antigo",
        re.compile(
            r"\bENUM\b.*\.create\s*\(\s*op\.get_bind\(\)",
            re.IGNORECASE | re.DOTALL,
        ),
        (
            "Use native_enum=False — evita CREATE TYPE completamente:\n"
            "  db.Column(db.Enum(MyEnum, name='x', native_enum=False))\n"
            "Ver: CLAUDE.md seção 'Migration Conventions'"
        ),
    ),
    (
        "gen_random_uuid() como server_default sem verificação de extensão",
        re.compile(
            r'server_default\s*=\s*sa\.text\(["\']gen_random_uuid\(\)["\']',
            re.IGNORECASE,
        ),
        (
            "gen_random_uuid() requer pgcrypto em PostgreSQL < 13.\n"
            "Prefira o default Python-side: default=uuid.uuid4 no modelo.\n"
            'Se precisar de server_default, use: sa.text("uuid_generate_v4()")\n'
            'com op.execute("CREATE EXTENSION IF NOT EXISTS \\"uuid-ossp\\"") antes.'
        ),
    ),
]


def check_file(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for name, pattern, suggestion in FORBIDDEN:
        if pattern.search(source):
            errors.append(
                f"\n  ✗ {name}\n"
                f"    Arquivo: {path}\n"
                f"    Sugestão:\n"
                + "\n".join(f"      {line}" for line in suggestion.splitlines())
            )
    return errors


def main() -> int:
    files = [Path(f) for f in sys.argv[1:] if f.endswith(".py")]
    if not files:
        return 0

    all_errors: list[str] = []
    for f in files:
        all_errors.extend(check_file(f))

    if all_errors:
        print(
            "\n[migration-pattern-check] Padrões proibidos detectados em migrations:\n"
            + "\n".join(all_errors)
            + "\n\nDocumentação: docs/wiki/Post-Mortem-PR1174-Bootstrap-Migration.md\n"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
