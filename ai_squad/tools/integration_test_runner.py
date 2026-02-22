#!/usr/bin/env python3
"""
Standalone integration test runner for Auraxis.

This script runs OUTSIDE the CrewAI venv, using the project's main venv
which has Flask, SQLAlchemy, etc. It is invoked by IntegrationTestTool
via safe_subprocess.

Usage:
    /path/to/project/.venv/bin/python integration_test_runner.py <scenario>

Available scenarios:
    register_and_login  — Register a user, login, verify token
    update_profile      — Register, login, update profile fields
    full_crud           — Register, login, update profile, read /me, verify data

Output: JSON with keys 'passed', 'steps', 'errors'
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# Resolve project root (ai_squad/tools/integration_test_runner.py → project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Ensure project root is in sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def setup_test_env():
    """Set up test environment variables."""
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(db_fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    test_env = {
        "SECRET_KEY": "test-secret-key-with-64-chars-minimum-for-jwt-signing-0001",
        "JWT_SECRET_KEY": "test-jwt-secret-key-with-64-chars-minimum-for-signing-0002",
        "FLASK_DEBUG": "False",
        "FLASK_TESTING": "true",
        "SECURITY_ENFORCE_STRONG_SECRETS": "false",
        "DOCS_EXPOSURE_POLICY": "public",
        "CORS_ALLOWED_ORIGINS": "https://frontend.local",
        "GRAPHQL_ALLOW_INTROSPECTION": "true",
        "BRAPI_CACHE_TTL_SECONDS": "0",
    }
    for key, value in test_env.items():
        os.environ[key] = value

    return db_path


def create_test_app():
    """Create a Flask test app with SQLite in-memory database."""
    from app import create_app
    from app.extensions.database import db

    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        db.drop_all()
        db.create_all()

    return app


def _append_step(
    results: dict[str, Any], action: str, status: int, passed: bool
) -> None:
    results["steps"].append({"action": action, "status": status, "passed": passed})
    if not passed:
        results["passed"] = False


def _register_user(client, results: dict[str, Any]) -> bool:
    payload = {
        "name": "Integration Test User",
        "email": "integration@test.com",
        "password": "TestSenha@123",
    }
    resp = client.post("/auth/register", json=payload, content_type="application/json")
    passed = resp.status_code == 201
    _append_step(results, "POST /auth/register", resp.status_code, passed)
    if not passed:
        body = resp.get_json() or {}
        results["errors"].append(
            f"Register failed ({resp.status_code}): "
            f"{json.dumps(body, ensure_ascii=False)[:300]}"
        )
    return passed


def _login_user(client, results: dict[str, Any]) -> str | None:
    payload = {"email": "integration@test.com", "password": "TestSenha@123"}
    resp = client.post("/auth/login", json=payload, content_type="application/json")
    body = resp.get_json() or {}
    token = None
    if resp.status_code == 200:
        token = body.get("token") or body.get("data", {}).get("token")
    passed = resp.status_code == 200 and token is not None
    _append_step(results, "POST /auth/login", resp.status_code, passed)
    if not passed:
        results["errors"].append(
            f"Login failed ({resp.status_code}): "
            f"{json.dumps(body, ensure_ascii=False)[:300]}"
        )
    return token


def _update_profile(client, headers: dict[str, str], results: dict[str, Any]) -> bool:
    payload = {
        "gender": "masculino",
        "birth_date": "1990-05-15",
        "monthly_income": "5000.00",
        "net_worth": "100000.00",
        "monthly_expenses": "2000.00",
        "state_uf": "SP",
        "occupation": "Engenheiro de Software",
        "investor_profile": "explorador",
    }
    resp = client.put(
        "/user/profile",
        json=payload,
        headers=headers,
        content_type="application/json",
    )
    passed = resp.status_code == 200
    _append_step(results, "PUT /user/profile", resp.status_code, passed)
    if not passed:
        body = resp.get_json() or {}
        results["errors"].append(
            f"Profile update failed ({resp.status_code}): "
            f"{json.dumps(body, ensure_ascii=False)[:300]}"
        )
    return passed


def _validate_me_payload(body: dict[str, Any], results: dict[str, Any]) -> None:
    user_data = body.get("data", {}).get("user", body.get("data", {}))
    if not isinstance(user_data, dict):
        return
    checks = {"gender": "masculino", "state_uf": "SP", "investor_profile": "explorador"}
    for field, expected in checks.items():
        actual = user_data.get(field)
        if actual != expected:
            results["errors"].append(
                f"Data mismatch: {field} expected '{expected}' got '{actual}'"
            )
            results["passed"] = False


def _read_me(client, headers: dict[str, str], results: dict[str, Any]) -> bool:
    resp = client.get("/user/me", headers=headers)
    body = resp.get_json() or {}
    passed = resp.status_code == 200
    _append_step(results, "GET /user/me", resp.status_code, passed)
    if not passed:
        results["errors"].append(
            f"Read /me failed ({resp.status_code}): "
            f"{json.dumps(body, ensure_ascii=False)[:300]}"
        )
        return False
    _validate_me_payload(body, results)
    return True


def run_scenario(app, scenario):
    """Execute an integration test scenario."""
    results = {"passed": True, "steps": [], "errors": []}

    with app.test_client() as client:
        if not _register_user(client, results):
            return results

        token = _login_user(client, results)
        if token is None:
            return results

        headers = {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}

        if scenario == "register_and_login":
            return results

        if not _update_profile(client, headers, results):
            return results

        if scenario == "update_profile":
            return results

        if scenario == "full_crud":
            _read_me(client, headers, results)

    return results


def cleanup(db_path):
    """Remove temporary database file."""
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except OSError:
        pass


def main():
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "passed": False,
                    "steps": [],
                    "errors": ["Usage: integration_test_runner.py <scenario>"],
                }
            )
        )
        sys.exit(1)

    scenario = sys.argv[1]
    valid = ("register_and_login", "update_profile", "full_crud")
    if scenario not in valid:
        print(
            json.dumps(
                {
                    "passed": False,
                    "steps": [],
                    "errors": [
                        f"Invalid scenario '{scenario}'. Valid: {', '.join(valid)}"
                    ],
                }
            )
        )
        sys.exit(1)

    db_path = setup_test_env()
    try:
        app = create_test_app()
        results = run_scenario(app, scenario)
    except Exception as e:
        results = {
            "passed": False,
            "steps": [],
            "errors": [f"Setup/execution error: {str(e)}"],
        }
    finally:
        cleanup(db_path)

    print(json.dumps(results, ensure_ascii=False))
    sys.exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
