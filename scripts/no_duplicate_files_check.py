#!/usr/bin/env python3
"""Pre-commit hook: bloqueia arquivos duplicados macOS criados por agentes de IA.

Padrão bloqueado: 'foo 2.py', 'foo 3.py', 'bar 2.yml', etc.
Causa raiz: agentes de IA escrevem em paths que já existem em worktrees
com symlinks; o macOS cria automaticamente cópias numeradas.
"""

from __future__ import annotations

import pathlib
import re
import sys

# Padrão: espaço + dígito(s) antes da extensão (ou no final do nome)
DUPLICATE_PATTERN = re.compile(r" \d+(\.[a-zA-Z0-9]+)?$")


def main() -> None:
    bad_files = [
        f for f in sys.argv[1:] if DUPLICATE_PATTERN.search(pathlib.Path(f).name)
    ]
    if not bad_files:
        sys.exit(0)

    print("BLOQUEADO: arquivos duplicados macOS detectados antes do commit:")
    for f in bad_files:
        print(f"  {f}")
    print(
        "\nEsses arquivos são artefatos criados pelo macOS quando agentes de IA"
        " escrevem em paths que já existem. Remova-os antes de commitar:\n"
        "  git rm --cached <arquivo>"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
