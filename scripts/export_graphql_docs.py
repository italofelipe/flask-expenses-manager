#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.graphql.docs_export import (  # noqa: E402
    GraphQLDocsSource,
    build_graphql_docs_bundle,
    read_committed_graphql_docs_bundle,
    write_graphql_docs_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta artefatos estáticos de documentação GraphQL.",
    )
    parser.add_argument(
        "--source",
        choices=("runtime", "sdl"),
        default="runtime",
        help="Fonte do schema usada para gerar os artefatos.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Falha se os artefatos versionados divergirem do bundle gerado.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = cast(GraphQLDocsSource, args.source)
    generated = build_graphql_docs_bundle(source)
    if args.check:
        committed = read_committed_graphql_docs_bundle()
        if committed != generated:
            print(
                "Artefatos GraphQL desatualizados. Rode "
                "`scripts/export_graphql_docs.py --source runtime`.",
                file=sys.stderr,
            )
            return 1
        return 0

    write_graphql_docs_bundle(generated)
    print(f"Artefatos GraphQL exportados com sucesso via source={source}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
