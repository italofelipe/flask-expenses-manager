#!/usr/bin/env python3
"""auraxis-api pre-tool-use hook — Python/Flask/SQLAlchemy safety guards."""

from __future__ import annotations

import json
import re
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENV_FILE_RE = re.compile(r"(^|/)\.env(?:\.(?!example$)[\w.-]+)?$")
_SENSITIVE = ("secrets.", "credentials.")
_INFRA_FILES = ("docker-compose", "Dockerfile", "run.py", "pyproject.toml")
_MIGRATION_PATTERNS = (
    "native_enum=True",
    "op.get_bind()",
    'op.execute("CREATE TYPE',
    "ENUM(",
    "gen_random_uuid()",
)
_CONTRACT_PATHS = (
    "app/models/",
    "app/schemas/",
    "openapi.json",
    "schema.graphql",
    "app/graphql/schema",
)
_COVERAGE_CONFIGS = ("pyproject.toml", ".coveragerc", "setup.cfg")

_HARD_BLOCKS = [
    (
        r"git add \.(\s|$)",
        "BLOQUEADO: 'git add .' proibido. Use: git add <arquivo>",
    ),
    (r"git add -A(\s|$)", "BLOQUEADO: 'git add -A' proibido."),
    (r"git add --all(\s|$)", "BLOQUEADO: 'git add --all' proibido."),
    (r"git push --force", "BLOQUEADO: push --force requer aprovacao humana."),
    (r"git push -f(\s|$)", "BLOQUEADO: push -f requer aprovacao humana."),
    (r"git commit --no-verify", "BLOQUEADO: --no-verify pula quality gates."),
    (r"git commit -n(\s|$)", "BLOQUEADO: -n pula quality gates."),
    (
        r"git push\s+(\S+\s+)?(main|master)(\s|$)",
        "BLOQUEADO: push direto para main/master. Use PR.",
    ),
    (r"DROP TABLE", "BLOQUEADO: DROP TABLE requer aprovacao humana."),
    (r"DROP DATABASE", "BLOQUEADO: DROP DATABASE requer aprovacao humana."),
    (
        r"flask db downgrade",
        "BLOQUEADO: downgrade de migration requer aprovacao humana.",
    ),
]

_SOFT_WARNS = [
    (r"git reset --hard", "AVISO: git reset --hard e destrutivo."),
    (r"rm -rf", "AVISO: rm -rf e destrutivo."),
    (
        r"flask db upgrade",
        "AVISO: flask db upgrade modifica o banco."
        " Confirme que scripts/test_migrations_local.sh passou.",
    ),
    (r"alembic upgrade", "AVISO: alembic upgrade modifica o banco."),
    (
        r"docker-compose.*down",
        "AVISO: docker-compose down pode destruir dados locais.",
    ),
]

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    if tool_name == "Bash":
        _check_bash(tool_input.get("command", ""))
    elif tool_name in ("Write", "Edit"):
        content = tool_input.get("content", "") or tool_input.get("new_string", "")
        _check_file_write(tool_input.get("file_path", ""), content=content)


# ---------------------------------------------------------------------------
# Bash guard
# ---------------------------------------------------------------------------


def _check_bash(command: str) -> None:
    for pattern, msg in _HARD_BLOCKS:
        if re.search(pattern, command):
            print(msg, file=sys.stderr)
            sys.exit(2)
    for pattern, msg in _SOFT_WARNS:
        if re.search(pattern, command):
            print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# File-write guards (split to keep each helper under complexity limit)
# ---------------------------------------------------------------------------


def _check_secrets(file_path: str) -> None:
    for s in _SENSITIVE:
        if s in file_path:
            print(
                f"BLOQUEADO: escrita em '{file_path}' proibida (secrets).",
                file=sys.stderr,
            )
            sys.exit(2)
    if _ENV_FILE_RE.search(file_path):
        print(
            f"BLOQUEADO: escrita em '{file_path}' proibida (.env).",
            file=sys.stderr,
        )
        sys.exit(2)


def _check_infra(file_path: str) -> None:
    for infra in _INFRA_FILES:
        if infra in file_path:
            print(
                f"AVISO: editando arquivo de infra '{file_path}'."
                " Requer aprovacao humana explicita.",
                file=sys.stderr,
            )


def _check_migration(file_path: str, content: str) -> None:
    if "migrations/" not in file_path or not content:
        return
    for pattern in _MIGRATION_PATTERNS:
        if pattern in content:
            print(
                f"AVISO: padrao problematico '{pattern}' em migration.\n"
                "Veja CLAUDE.md 'Migration Conventions' — use native_enum=False"
                " e teste com scripts/test_migrations_local.sh",
                file=sys.stderr,
            )


def _check_contract(file_path: str) -> None:
    for cp in _CONTRACT_PATHS:
        if cp in file_path:
            print(
                f"AVISO: editando fonte de contrato '{file_path}'.\n"
                "Atualize o snapshot OpenAPI e valide consumers"
                " (auraxis-web, auraxis-app).",
                file=sys.stderr,
            )
            return


def _check_coverage_config(file_path: str) -> None:
    for cc in _COVERAGE_CONFIGS:
        if file_path.endswith(cc):
            print(
                f"AVISO: editando config de qualidade '{file_path}'."
                " Threshold minimo: 85%.",
                file=sys.stderr,
            )


def _check_file_write(file_path: str, content: str = "") -> None:
    _check_secrets(file_path)
    _check_infra(file_path)
    _check_migration(file_path, content)
    _check_contract(file_path)
    _check_coverage_config(file_path)


if __name__ == "__main__":
    main()
