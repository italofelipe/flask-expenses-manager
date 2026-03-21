from __future__ import annotations

from pathlib import Path

from app.graphql.authorization import (
    DEFAULT_GRAPHQL_PUBLIC_MUTATIONS,
    DEFAULT_GRAPHQL_PUBLIC_QUERIES,
)

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE_PATHS = (
    ROOT / ".env.dev.example",
    ROOT / ".env.prod.example",
)


def _read_public_queries(path: Path) -> set[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("GRAPHQL_PUBLIC_QUERIES="):
            _, value = line.split("=", maxsplit=1)
            return {item.strip() for item in value.split(",") if item.strip()}
    raise AssertionError(f"GRAPHQL_PUBLIC_QUERIES não encontrado em {path}")


def test_env_examples_allow_public_installment_vs_cash_query() -> None:
    for path in ENV_EXAMPLE_PATHS:
        public_queries = _read_public_queries(path)
        assert "installmentVsCashCalculate" in public_queries


def _read_public_mutations(path: Path) -> set[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("GRAPHQL_PUBLIC_MUTATIONS="):
            _, value = line.split("=", maxsplit=1)
            return {item.strip() for item in value.split(",") if item.strip()}
    raise AssertionError(f"GRAPHQL_PUBLIC_MUTATIONS não encontrado em {path}")


def test_env_examples_match_graphql_public_defaults() -> None:
    for path in ENV_EXAMPLE_PATHS:
        assert _read_public_queries(path) == set(DEFAULT_GRAPHQL_PUBLIC_QUERIES)
        assert _read_public_mutations(path) == set(DEFAULT_GRAPHQL_PUBLIC_MUTATIONS)
