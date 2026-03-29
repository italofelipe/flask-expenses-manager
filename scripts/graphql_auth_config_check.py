#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION_PATH = ROOT / "app/graphql/authorization.py"
ENV_EXAMPLE_PATHS = (
    ROOT / ".env.dev.example",
    ROOT / ".env.prod.example",
)


def _read_default_set(name: str) -> set[str]:
    module = ast.parse(AUTHORIZATION_PATH.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                call = node.value
                if not isinstance(call, ast.Call) or not call.args:
                    raise SystemExit(
                        f"{name} tem formato inesperado em {AUTHORIZATION_PATH}"
                    )
                values_node = call.args[0]
                if not isinstance(values_node, ast.Set):
                    raise SystemExit(
                        f"{name} deve ser definido com set literal em "
                        f"{AUTHORIZATION_PATH}"
                    )
                values: set[str] = set()
                for elt in values_node.elts:
                    if not isinstance(elt, ast.Constant) or not isinstance(
                        elt.value, str
                    ):
                        raise SystemExit(
                            f"{name} contém valor não suportado em {AUTHORIZATION_PATH}"
                        )
                    values.add(elt.value)
                return values
    raise SystemExit(f"{name} não encontrado em {AUTHORIZATION_PATH}")


def _read_csv_setting(path: Path, setting_name: str) -> set[str]:
    prefix = f"{setting_name}="
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            _, value = line.split("=", maxsplit=1)
            return {item.strip() for item in value.split(",") if item.strip()}
    raise SystemExit(f"{setting_name} não encontrado em {path}")


def main() -> int:
    default_public_queries = _read_default_set("DEFAULT_GRAPHQL_PUBLIC_QUERIES")
    default_public_mutations = _read_default_set("DEFAULT_GRAPHQL_PUBLIC_MUTATIONS")
    for path in ENV_EXAMPLE_PATHS:
        public_queries = _read_csv_setting(path, "GRAPHQL_PUBLIC_QUERIES")
        public_mutations = _read_csv_setting(path, "GRAPHQL_PUBLIC_MUTATIONS")
        if public_queries != default_public_queries:
            raise SystemExit(
                f"{path} está desalinhado em GRAPHQL_PUBLIC_QUERIES: "
                f"{sorted(public_queries)} != {sorted(default_public_queries)}"
            )
        if public_mutations != default_public_mutations:
            raise SystemExit(
                f"{path} está desalinhado em GRAPHQL_PUBLIC_MUTATIONS: "
                f"{sorted(public_mutations)} != {sorted(default_public_mutations)}"
            )
    print("[graphql-auth-config-check] ok: env examples aligned with GraphQL defaults")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
