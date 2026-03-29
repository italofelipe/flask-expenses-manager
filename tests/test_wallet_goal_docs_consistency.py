from __future__ import annotations

from pathlib import Path


def _read_doc(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_wallet_and_goal_docs_expose_canonical_patch_and_legacy_aliases() -> None:
    api_doc = _read_doc("docs/API_DOCUMENTATION.md")
    goal_doc = _read_doc("docs/controllers/goal_controller.md")
    wallet_doc = _read_doc("docs/controllers/wallet_controller.md")

    assert "PATCH /goals/{goal_id}" in api_doc
    assert "`PUT /goals/{goal_id}` (alias legado)" in api_doc
    assert "`PATCH /wallet/{investment_id}`" in api_doc
    assert "`PUT /wallet/{investment_id}`" in api_doc
    assert "start_date" in api_doc
    assert "startDate" in api_doc
    assert "GoalResource.patch" in goal_doc
    assert "Alias legado para atualização parcial de uma meta especifica." in goal_doc
    assert "`PATCH /wallet/{investment_id}`" in wallet_doc
    assert "start_date" in wallet_doc
    assert "startDate" in wallet_doc
