from __future__ import annotations

import json
from pathlib import Path


def _load_postman_items() -> list[dict[str, object]]:
    collection_path = (
        Path(__file__).resolve().parents[1]
        / "api-tests"
        / "postman"
        / "auraxis.postman_collection.json"
    )
    payload = json.loads(collection_path.read_text())
    items = payload.get("item")
    assert isinstance(items, list)
    return items


def test_postman_collection_covers_installment_vs_cash_rest_and_graphql() -> None:
    items = _load_postman_items()
    names = {str(item.get("name")) for item in items}

    assert "12 - Installment vs Cash calculate (REST public)" in names
    assert "13 - Installment vs Cash save (REST auth required)" in names
    assert "14 - GraphQL installment vs cash calculate (public)" in names
    assert "15 - GraphQL installment vs cash save (auth required)" in names
