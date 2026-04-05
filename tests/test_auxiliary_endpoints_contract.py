from __future__ import annotations

from uuid import uuid4


def _register_and_login(client, *, prefix: str) -> str:
    suffix = uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    register = client.post(
        "/auth/register",
        json={"name": f"user-{suffix}", "email": email, "password": password},
    )
    assert register.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-API-Contract": "v2",
    }


def _exercise_named_crud_resource(
    client,
    *,
    auth_prefix: str,
    base_path: str,
    collection_key: str,
    entity_key: str,
    create_message: str,
    update_message: str,
    delete_message: str,
    not_found_message: str,
    name_limit: int,
) -> None:
    token = _register_and_login(client, prefix=auth_prefix)
    headers = _auth_headers(token)

    initial = client.get(base_path, headers=headers)
    assert initial.status_code == 200
    initial_body = initial.get_json()
    assert initial_body["success"] is True
    assert initial_body["data"][collection_key] == []
    assert initial_body["data"]["total"] == 0

    missing_name = client.post(base_path, json={}, headers=headers)
    assert missing_name.status_code == 400
    assert missing_name.get_json()["error"]["code"] == "MISSING_NAME"

    too_long_name = client.post(
        base_path,
        json={"name": "x" * (name_limit + 1)},
        headers=headers,
    )
    assert too_long_name.status_code == 400
    assert too_long_name.get_json()["error"]["code"] == "NAME_TOO_LONG"

    created = client.post(base_path, json={"name": "Principal"}, headers=headers)
    assert created.status_code == 201
    created_body = created.get_json()
    assert created_body["message"] == create_message
    entity_id = created_body["data"][entity_key]["id"]

    listed = client.get(base_path, headers=headers)
    assert listed.status_code == 200
    listed_body = listed.get_json()
    assert listed_body["data"]["total"] == 1
    assert listed_body["data"][collection_key][0]["id"] == entity_id

    missing_update_name = client.put(
        f"{base_path}/{entity_id}",
        json={},
        headers=headers,
    )
    assert missing_update_name.status_code == 400
    assert missing_update_name.get_json()["error"]["code"] == "MISSING_NAME"

    too_long_update_name = client.put(
        f"{base_path}/{entity_id}",
        json={"name": "y" * (name_limit + 1)},
        headers=headers,
    )
    assert too_long_update_name.status_code == 400
    assert too_long_update_name.get_json()["error"]["code"] == "NAME_TOO_LONG"

    missing_entity_id = str(uuid4())
    missing_update = client.put(
        f"{base_path}/{missing_entity_id}",
        json={"name": "Updated"},
        headers=headers,
    )
    assert missing_update.status_code == 404
    assert missing_update.get_json()["message"] == not_found_message

    updated = client.put(
        f"{base_path}/{entity_id}",
        json={"name": "Updated"},
        headers=headers,
    )
    assert updated.status_code == 200
    updated_body = updated.get_json()
    assert updated_body["message"] == update_message
    assert updated_body["data"][entity_key]["name"] == "Updated"

    missing_delete = client.delete(f"{base_path}/{missing_entity_id}", headers=headers)
    assert missing_delete.status_code == 404
    assert missing_delete.get_json()["message"] == not_found_message

    deleted = client.delete(f"{base_path}/{entity_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.get_json()["message"] == delete_message

    final = client.get(base_path, headers=headers)
    assert final.status_code == 200
    final_body = final.get_json()
    assert final_body["data"][collection_key] == []
    assert final_body["data"]["total"] == 0


def test_accounts_crud_contract(client) -> None:
    _exercise_named_crud_resource(
        client,
        auth_prefix="accounts-crud",
        base_path="/accounts",
        collection_key="accounts",
        entity_key="account",
        create_message="Conta criada com sucesso",
        update_message="Conta atualizada com sucesso",
        delete_message="Conta removida com sucesso",
        not_found_message="Account not found",
        name_limit=100,
    )


def test_credit_cards_crud_contract(client) -> None:
    _exercise_named_crud_resource(
        client,
        auth_prefix="credit-cards-crud",
        base_path="/credit-cards",
        collection_key="credit_cards",
        entity_key="credit_card",
        create_message="Cartão criado com sucesso",
        update_message="Cartão atualizado com sucesso",
        delete_message="Cartão removido com sucesso",
        not_found_message="Credit card not found",
        name_limit=100,
    )


def test_tags_crud_contract(client) -> None:
    """Tag CRUD contract — accounts for 8 default seed tags created on registration."""
    from uuid import uuid4 as _uuid4

    token = _register_and_login(client, prefix="tags-crud")
    headers = _auth_headers(token)

    # Registration now seeds 8 default tags
    initial = client.get("/tags", headers=headers)
    assert initial.status_code == 200
    initial_body = initial.get_json()
    assert initial_body["success"] is True
    seed_count = len(initial_body["data"]["tags"])
    assert seed_count == 8
    assert initial_body["data"]["total"] == 8

    # Validation errors still work the same
    missing_name = client.post("/tags", json={}, headers=headers)
    assert missing_name.status_code == 400
    assert missing_name.get_json()["error"]["code"] == "MISSING_NAME"

    too_long_name = client.post("/tags", json={"name": "x" * 51}, headers=headers)
    assert too_long_name.status_code == 400
    assert too_long_name.get_json()["error"]["code"] == "NAME_TOO_LONG"

    # Create a new tag
    created = client.post("/tags", json={"name": "Principal"}, headers=headers)
    assert created.status_code == 201
    created_body = created.get_json()
    assert created_body["message"] == "Tag criada com sucesso"
    tag_id = created_body["data"]["tag"]["id"]

    listed = client.get("/tags", headers=headers)
    assert listed.status_code == 200
    listed_body = listed.get_json()
    assert listed_body["data"]["total"] == seed_count + 1

    # Update
    missing_update_name = client.put(f"/tags/{tag_id}", json={}, headers=headers)
    assert missing_update_name.status_code == 400
    assert missing_update_name.get_json()["error"]["code"] == "MISSING_NAME"

    too_long_update_name = client.put(
        f"/tags/{tag_id}", json={"name": "y" * 51}, headers=headers
    )
    assert too_long_update_name.status_code == 400
    assert too_long_update_name.get_json()["error"]["code"] == "NAME_TOO_LONG"

    missing_id = str(_uuid4())
    missing_update = client.put(
        f"/tags/{missing_id}", json={"name": "Updated"}, headers=headers
    )
    assert missing_update.status_code == 404
    assert missing_update.get_json()["message"] == "Tag not found"

    updated = client.put(f"/tags/{tag_id}", json={"name": "Updated"}, headers=headers)
    assert updated.status_code == 200
    updated_body = updated.get_json()
    assert updated_body["message"] == "Tag atualizada com sucesso"
    assert updated_body["data"]["tag"]["name"] == "Updated"

    # Delete
    missing_delete = client.delete(f"/tags/{missing_id}", headers=headers)
    assert missing_delete.status_code == 404
    assert missing_delete.get_json()["message"] == "Tag not found"

    deleted = client.delete(f"/tags/{tag_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.get_json()["message"] == "Tag removida com sucesso"

    # Back to seed count
    final = client.get("/tags", headers=headers)
    assert final.status_code == 200
    final_body = final.get_json()
    assert final_body["data"]["total"] == seed_count
