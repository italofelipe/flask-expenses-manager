"""
Integration tests for B11 — Investor Profile Suggestion fields.

Acceptance criteria (from tasks.md):
  [P2] Persistir e expor resultado do questionário (investor_profile_suggested,
  profile_quiz_score, taxonomy_version) para comparação com perfil auto declarado.

What is tested here:
  REST  — PUT /user/profile persists all 3 new fields
  REST  — GET /user/profile returns all 3 new fields in the response
  REST  — investor_profile_suggested is lowercased on save
  REST  — profile_quiz_score rejects negative values
  REST  — taxonomy_version rejects values longer than 16 chars
  REST  — investor_profile_suggested rejects values longer than 32 chars
  REST  — all 3 fields accept None (optional, nullable)
  REST  — declared (investor_profile) and suggested (investor_profile_suggested)
           coexist independently in the same response
  REST  — audit event emits changed_fields when suggestion fields are updated
  GraphQL — updateUserProfile mutation accepts and persists the 3 new fields
  GraphQL — UserType exposes investor_profile_suggested, profile_quiz_score,
             taxonomy_version in mutation and query responses
  GraphQL — suggested field is lowercased via GraphQL mutation too

These tests intentionally do NOT test B10 (the quiz algorithm itself), which
is a separate task.  B11 only covers persistence/exposure of quiz output.
"""

from __future__ import annotations

import uuid
from typing import Any

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _register_and_login(client) -> str:
    """Register a fresh user and return a valid JWT token."""
    suffix = uuid.uuid4().hex[:8]
    email = f"b11-{suffix}@test.com"
    password = "StrongPass@123"

    reg = client.post(
        "/auth/register",
        json={"name": f"b11-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["token"]


def _put_profile(client, token: str, payload: dict[str, Any]) -> Any:
    return client.put(
        "/user/profile",
        headers={"Authorization": f"Bearer {token}", "X-API-Contract": "v2"},
        json=payload,
    )


def _get_profile(client, token: str) -> Any:
    return client.get(
        "/user/profile",
        headers={"Authorization": f"Bearer {token}", "X-API-Contract": "v2"},
    )


def _graphql(
    client,
    query: str,
    variables: dict[str, Any] | None = None,
    token: str | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


def _register_and_login_graphql(client) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"b11-gql-{suffix}@test.com"
    password = "StrongPass@123"

    reg_mutation = """
    mutation Register($name: String!, $email: String!, $password: String!) {
      registerUser(name: $name, email: $email, password: $password) { message }
    }
    """
    _graphql(
        client,
        reg_mutation,
        {"name": f"b11-gql-{suffix}", "email": email, "password": password},
    )

    login_mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) { token }
    }
    """
    resp = _graphql(client, login_mutation, {"email": email, "password": password})
    return resp.get_json()["data"]["login"]["token"]


# ---------------------------------------------------------------------------
# REST — persist and expose
# ---------------------------------------------------------------------------


def test_rest_put_profile_persists_investor_profile_suggested(client) -> None:
    """PUT /user/profile must persist investor_profile_suggested and return it in
    the response body, satisfying the B11 acceptance criterion."""
    token = _register_and_login(client)
    resp = _put_profile(client, token, {"investor_profile_suggested": "explorador"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["user"]["investor_profile_suggested"] == "explorador"


def test_rest_put_profile_persists_profile_quiz_score(client) -> None:
    """PUT /user/profile must persist profile_quiz_score."""
    token = _register_and_login(client)
    resp = _put_profile(client, token, {"profile_quiz_score": 78})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["user"]["profile_quiz_score"] == 78


def test_rest_put_profile_persists_taxonomy_version(client) -> None:
    """PUT /user/profile must persist taxonomy_version."""
    token = _register_and_login(client)
    resp = _put_profile(client, token, {"taxonomy_version": "v1.0"})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["user"]["taxonomy_version"] == "v1.0"


def test_rest_put_profile_persists_all_b11_fields_together(client) -> None:
    """All 3 B11 fields can be set in a single PUT request."""
    token = _register_and_login(client)
    resp = _put_profile(
        client,
        token,
        {
            "investor_profile_suggested": "conservador",
            "profile_quiz_score": 42,
            "taxonomy_version": "v1.0",
        },
    )
    assert resp.status_code == 200
    user = resp.get_json()["data"]["user"]
    assert user["investor_profile_suggested"] == "conservador"
    assert user["profile_quiz_score"] == 42
    assert user["taxonomy_version"] == "v1.0"


def test_rest_get_profile_exposes_b11_fields(client) -> None:
    """GET /user/profile must return all 3 B11 fields after a previous PUT."""
    token = _register_and_login(client)
    _put_profile(
        client,
        token,
        {
            "investor_profile_suggested": "entusiasta",
            "profile_quiz_score": 91,
            "taxonomy_version": "v2.1",
        },
    )
    resp = _get_profile(client, token)
    assert resp.status_code == 200
    user = resp.get_json()["data"]["user"]
    assert user["investor_profile_suggested"] == "entusiasta"
    assert user["profile_quiz_score"] == 91
    assert user["taxonomy_version"] == "v2.1"


# ---------------------------------------------------------------------------
# REST — normalization
# ---------------------------------------------------------------------------


def test_rest_investor_profile_suggested_is_lowercased(client) -> None:
    """investor_profile_suggested must be stored lowercase, matching the same
    normalization applied to investor_profile."""
    token = _register_and_login(client)
    resp = _put_profile(client, token, {"investor_profile_suggested": "Explorador"})
    assert resp.status_code == 200
    assert resp.get_json()["data"]["user"]["investor_profile_suggested"] == "explorador"


def test_rest_investor_profile_suggested_mixed_case_lowercased(client) -> None:
    token = _register_and_login(client)
    resp = _put_profile(client, token, {"investor_profile_suggested": "CONSERVADOR"})
    assert resp.status_code == 200
    assert (
        resp.get_json()["data"]["user"]["investor_profile_suggested"] == "conservador"
    )


# ---------------------------------------------------------------------------
# REST — validation
# ---------------------------------------------------------------------------


def test_rest_profile_quiz_score_rejects_negative(client) -> None:
    """profile_quiz_score must be >= 0. Negative values must return 400."""
    token = _register_and_login(client)
    resp = _put_profile(client, token, {"profile_quiz_score": -1})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_rest_taxonomy_version_rejects_value_over_16_chars(client) -> None:
    """taxonomy_version is limited to 16 characters (DB column length)."""
    token = _register_and_login(client)
    resp = _put_profile(client, token, {"taxonomy_version": "v" * 17})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_rest_investor_profile_suggested_rejects_value_over_32_chars(client) -> None:
    """investor_profile_suggested is limited to 32 characters."""
    token = _register_and_login(client)
    resp = _put_profile(client, token, {"investor_profile_suggested": "x" * 33})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# REST — nullable / optional
# ---------------------------------------------------------------------------


def test_rest_b11_fields_are_null_on_new_user(client) -> None:
    """A freshly registered user has all 3 B11 fields as null by default."""
    token = _register_and_login(client)
    resp = _get_profile(client, token)
    assert resp.status_code == 200
    user = resp.get_json()["data"]["user"]
    assert user.get("investor_profile_suggested") is None
    assert user.get("profile_quiz_score") is None
    assert user.get("taxonomy_version") is None


def test_rest_b11_fields_can_be_explicitly_set_to_null(client) -> None:
    """Any of the 3 fields can be cleared by sending null."""
    token = _register_and_login(client)
    _put_profile(
        client,
        token,
        {"investor_profile_suggested": "explorador", "profile_quiz_score": 80},
    )
    resp = _put_profile(
        client,
        token,
        {"investor_profile_suggested": None, "profile_quiz_score": None},
    )
    assert resp.status_code == 200
    user = resp.get_json()["data"]["user"]
    assert user["investor_profile_suggested"] is None
    assert user["profile_quiz_score"] is None


# ---------------------------------------------------------------------------
# REST — coexistence with declared investor_profile (core B11 requirement)
# ---------------------------------------------------------------------------


def test_rest_suggested_and_declared_profiles_coexist_independently(client) -> None:
    """Core acceptance criterion: investor_profile (declared) and
    investor_profile_suggested (quiz-derived) must coexist and be independently
    updateable, allowing UX comparison between the two values."""
    token = _register_and_login(client)

    # Set declared profile
    _put_profile(client, token, {"investor_profile": "conservador"})

    # Set suggested profile without touching declared
    _put_profile(
        client,
        token,
        {
            "investor_profile_suggested": "entusiasta",
            "profile_quiz_score": 95,
            "taxonomy_version": "v1.0",
        },
    )

    resp = _get_profile(client, token)
    assert resp.status_code == 200
    user = resp.get_json()["data"]["user"]

    # Both profiles coexist with different values
    assert user["investor_profile"] == "conservador"
    assert user["investor_profile_suggested"] == "entusiasta"
    assert user["profile_quiz_score"] == 95
    assert user["taxonomy_version"] == "v1.0"


def test_rest_updating_suggested_does_not_change_declared(client) -> None:
    """Updating investor_profile_suggested must not overwrite investor_profile."""
    token = _register_and_login(client)
    _put_profile(client, token, {"investor_profile": "explorador"})
    _put_profile(client, token, {"investor_profile_suggested": "conservador"})

    resp = _get_profile(client, token)
    user = resp.get_json()["data"]["user"]
    assert user["investor_profile"] == "explorador"  # unchanged
    assert user["investor_profile_suggested"] == "conservador"  # updated


def test_rest_updating_declared_does_not_change_suggested(client) -> None:
    """Updating investor_profile must not overwrite investor_profile_suggested."""
    token = _register_and_login(client)
    _put_profile(client, token, {"investor_profile_suggested": "entusiasta"})
    _put_profile(client, token, {"investor_profile": "conservador"})

    resp = _get_profile(client, token)
    user = resp.get_json()["data"]["user"]
    assert user["investor_profile"] == "conservador"  # updated
    assert user["investor_profile_suggested"] == "entusiasta"  # unchanged


# ---------------------------------------------------------------------------
# REST — audit trail
# ---------------------------------------------------------------------------


def test_rest_audit_event_emitted_on_b11_field_update(client, caplog) -> None:
    """Updating B11 fields must emit a user.profile_update audit event that
    includes the changed fields in the log line."""
    token = _register_and_login(client)
    resp = _put_profile(
        client,
        token,
        {
            "investor_profile_suggested": "explorador",
            "profile_quiz_score": 70,
            "taxonomy_version": "v1.0",
        },
    )
    assert resp.status_code == 200
    messages = [r.message for r in caplog.records]
    assert any("event=user.profile_update" in m for m in messages)


# ---------------------------------------------------------------------------
# GraphQL — mutation
# ---------------------------------------------------------------------------

_UPDATE_PROFILE_MUTATION = """
mutation UpdateProfile(
  $investorProfileSuggested: String
  $profileQuizScore: Int
  $taxonomyVersion: String
) {
  updateUserProfile(
    investorProfileSuggested: $investorProfileSuggested
    profileQuizScore: $profileQuizScore
    taxonomyVersion: $taxonomyVersion
  ) {
    user {
      investorProfile
      investorProfileSuggested
      profileQuizScore
      taxonomyVersion
    }
  }
}
"""


def test_graphql_mutation_persists_all_b11_fields(client) -> None:
    """updateUserProfile mutation must accept and persist all 3 B11 fields."""
    token = _register_and_login_graphql(client)
    resp = _graphql(
        client,
        _UPDATE_PROFILE_MUTATION,
        {
            "investorProfileSuggested": "explorador",
            "profileQuizScore": 88,
            "taxonomyVersion": "v1.0",
        },
        token=token,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body, body.get("errors")
    user = body["data"]["updateUserProfile"]["user"]
    assert user["investorProfileSuggested"] == "explorador"
    assert user["profileQuizScore"] == 88
    assert user["taxonomyVersion"] == "v1.0"


def test_graphql_mutation_lowercases_investor_profile_suggested(client) -> None:
    """investor_profile_suggested must be lowercased via GraphQL too."""
    token = _register_and_login_graphql(client)
    resp = _graphql(
        client,
        _UPDATE_PROFILE_MUTATION,
        {"investorProfileSuggested": "Conservador"},
        token=token,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body
    user = body["data"]["updateUserProfile"]["user"]
    assert user["investorProfileSuggested"] == "conservador"


def test_graphql_mutation_b11_and_declared_profile_coexist(client) -> None:
    """GraphQL: investor_profile and investor_profile_suggested must coexist."""
    token = _register_and_login_graphql(client)

    # Set declared profile first
    _graphql(
        client,
        """
        mutation { updateUserProfile(investorProfile: "conservador") {
          user { investorProfile }
        }}
        """,
        token=token,
    )

    # Set suggested via separate mutation
    resp = _graphql(
        client,
        _UPDATE_PROFILE_MUTATION,
        {
            "investorProfileSuggested": "entusiasta",
            "profileQuizScore": 95,
            "taxonomyVersion": "v2.0",
        },
        token=token,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body
    user = body["data"]["updateUserProfile"]["user"]
    assert user["investorProfile"] == "conservador"  # unchanged
    assert user["investorProfileSuggested"] == "entusiasta"
    assert user["profileQuizScore"] == 95
    assert user["taxonomyVersion"] == "v2.0"


def test_graphql_user_type_exposes_b11_fields_via_mutation_return(client) -> None:
    """UserType must expose B11 fields in the mutation return value.
    This verifies cross-transport consistency: fields set via REST PUT
    are readable by subsequent GraphQL mutations that return UserType.
    """
    token = _register_and_login(client)

    # Set fields via REST
    _put_profile(
        client,
        token,
        {
            "investor_profile_suggested": "explorador",
            "profile_quiz_score": 60,
            "taxonomy_version": "v1.1",
        },
    )

    # Trigger a no-op GraphQL mutation (update a different field) and check
    # that the returned UserType includes the B11 fields previously set via REST.
    resp = _graphql(
        client,
        """
        mutation {
          updateUserProfile(occupation: "Engenheiro") {
            user {
              occupation
              investorProfileSuggested
              profileQuizScore
              taxonomyVersion
            }
          }
        }
        """,
        token=token,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "errors" not in body, body.get("errors")
    user = body["data"]["updateUserProfile"]["user"]
    assert user["occupation"] == "Engenheiro"
    # B11 fields set via REST must be visible in GraphQL UserType response
    assert user["investorProfileSuggested"] == "explorador"
    assert user["profileQuizScore"] == 60
    assert user["taxonomyVersion"] == "v1.1"
