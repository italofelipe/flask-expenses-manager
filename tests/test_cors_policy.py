from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from flask import Flask, jsonify

from app.middleware.cors import (
    CorsPolicy,
    _build_cors_policy_from_env,
    _is_allowed_origin,
    _parse_allowed_origins,
    _read_bool_env,
    _validate_cors_policy,
    register_cors,
)


def _build_app() -> Flask:
    app = Flask(__name__)

    @app.route("/ping", methods=["GET", "OPTIONS"])
    def ping() -> Any:
        return jsonify({"ok": True})

    return app


def test_parse_allowed_origins_handles_empty_and_whitespace() -> None:
    assert _parse_allowed_origins(None) == set()
    assert _parse_allowed_origins("") == set()
    assert _parse_allowed_origins(" ,  , ") == set()
    assert _parse_allowed_origins("https://a.com, https://b.com ") == {
        "https://a.com",
        "https://b.com",
    }


def test_read_bool_env_uses_default_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AURAXIS_FLAG", raising=False)
    assert _read_bool_env("AURAXIS_FLAG", True) is True
    assert _read_bool_env("AURAXIS_FLAG", False) is False


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
def test_read_bool_env_true_values(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("AURAXIS_FLAG", raw)
    assert _read_bool_env("AURAXIS_FLAG", False) is True


@pytest.mark.parametrize("raw", ["0", "false", "no", "off", "anything-else"])
def test_read_bool_env_false_values(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("AURAXIS_FLAG", raw)
    assert _read_bool_env("AURAXIS_FLAG", True) is False


def test_build_cors_policy_from_env_respects_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.delenv("FLASK_TESTING", raising=False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://api.auraxis.com.br")
    monkeypatch.delenv("CORS_ALLOW_CREDENTIALS", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_METHODS", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_HEADERS", raising=False)
    monkeypatch.delenv("CORS_MAX_AGE_SECONDS", raising=False)

    policy = _build_cors_policy_from_env()

    assert policy.allowed_origins == {"https://api.auraxis.com.br"}
    assert policy.allow_credentials is True
    assert policy.allow_methods == "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    assert policy.allow_headers == "Authorization,Content-Type,X-API-Contract"
    assert policy.max_age_seconds == 600
    assert policy.is_production is True


def test_build_cors_policy_marks_non_production_when_testing_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "true")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")
    policy = _build_cors_policy_from_env()
    assert policy.is_production is False


def test_validate_cors_policy_blocks_wildcard_with_credentials() -> None:
    policy = CorsPolicy(
        allowed_origins={"*"},
        allow_credentials=True,
        allow_methods="GET",
        allow_headers="Authorization",
        max_age_seconds=600,
        is_production=False,
    )
    with pytest.raises(RuntimeError):
        _validate_cors_policy(policy)


def test_validate_cors_policy_allows_production_with_explicit_origin() -> None:
    policy = CorsPolicy(
        allowed_origins={"https://frontend.auraxis.com.br"},
        allow_credentials=False,
        allow_methods="GET",
        allow_headers="Authorization",
        max_age_seconds=600,
        is_production=True,
    )
    _validate_cors_policy(policy)


def test_validate_cors_policy_requires_origins_in_production() -> None:
    policy = CorsPolicy(
        allowed_origins=set(),
        allow_credentials=False,
        allow_methods="GET",
        allow_headers="Authorization",
        max_age_seconds=600,
        is_production=True,
    )
    with pytest.raises(RuntimeError):
        _validate_cors_policy(policy)


def test_validate_cors_policy_blocks_wildcard_in_production() -> None:
    policy = CorsPolicy(
        allowed_origins={"*"},
        allow_credentials=False,
        allow_methods="GET",
        allow_headers="Authorization",
        max_age_seconds=600,
        is_production=True,
    )
    with pytest.raises(RuntimeError):
        _validate_cors_policy(policy)


def test_validate_cors_policy_allows_non_prod_wildcard_without_credentials() -> None:
    policy = CorsPolicy(
        allowed_origins={"*"},
        allow_credentials=False,
        allow_methods="GET",
        allow_headers="Authorization",
        max_age_seconds=600,
        is_production=False,
    )
    _validate_cors_policy(policy)


def test_cors_policy_is_immutable() -> None:
    policy = CorsPolicy(
        allowed_origins={"https://frontend.auraxis.com.br"},
        allow_credentials=True,
        allow_methods="GET,POST",
        allow_headers="Authorization",
        max_age_seconds=600,
        is_production=False,
    )

    with pytest.raises(FrozenInstanceError):
        policy.allow_methods = "GET"  # type: ignore[misc]


def test_is_allowed_origin_accepts_exact_and_wildcard() -> None:
    assert _is_allowed_origin("https://allowed.com", {"https://allowed.com"}) is True
    assert _is_allowed_origin("https://any.com", {"*"}) is True
    assert _is_allowed_origin("https://denied.com", {"https://allowed.com"}) is False


def test_register_cors_applies_headers_for_allowed_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setenv("FLASK_TESTING", "true")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://frontend.auraxis.com.br")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")
    monkeypatch.setenv("CORS_ALLOWED_METHODS", "GET,POST,OPTIONS")
    monkeypatch.setenv("CORS_ALLOWED_HEADERS", "Authorization,Content-Type")
    monkeypatch.setenv("CORS_MAX_AGE_SECONDS", "1200")

    app = _build_app()
    register_cors(app)
    client = app.test_client()

    response = client.get(
        "/ping",
        headers={"Origin": "https://frontend.auraxis.com.br"},
    )

    assert response.status_code == 200
    assert (
        response.headers.get("Access-Control-Allow-Origin")
        == "https://frontend.auraxis.com.br"
    )
    assert response.headers.get("Access-Control-Allow-Credentials") == "true"
    assert response.headers.get("Access-Control-Allow-Methods") == "GET,POST,OPTIONS"
    assert response.headers.get("Access-Control-Allow-Headers") == (
        "Authorization,Content-Type"
    )
    assert response.headers.get("Access-Control-Max-Age") == "1200"
    assert response.headers.get("Vary") == "Origin"


def test_register_cors_skips_headers_for_disallowed_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setenv("FLASK_TESTING", "true")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://frontend.auraxis.com.br")

    app = _build_app()
    register_cors(app)
    client = app.test_client()

    response = client.get("/ping", headers={"Origin": "https://malicious.example"})
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers


def test_register_cors_handles_preflight_for_allowed_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "true")
    monkeypatch.setenv("FLASK_TESTING", "true")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://frontend.auraxis.com.br")

    app = _build_app()
    register_cors(app)
    client = app.test_client()

    response = client.options(
        "/ping",
        headers={"Origin": "https://frontend.auraxis.com.br"},
    )
    assert response.status_code == 204
    assert (
        response.headers.get("Access-Control-Allow-Origin")
        == "https://frontend.auraxis.com.br"
    )


def test_register_cors_rejects_invalid_production_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("FLASK_TESTING", "false")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    app = _build_app()
    with pytest.raises(RuntimeError):
        register_cors(app)
