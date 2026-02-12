import os
import sys
from pathlib import Path
from typing import Generator

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

TEST_ENV_OVERRIDES = {
    "SECRET_KEY": "test-secret",
    "JWT_SECRET_KEY": "test-jwt-secret",
    "FLASK_DEBUG": "False",
    "FLASK_TESTING": "true",
    "SECURITY_ENFORCE_STRONG_SECRETS": "false",
    "DOCS_EXPOSURE_POLICY": "public",
    "CORS_ALLOWED_ORIGINS": "https://frontend.local",
    "GRAPHQL_ALLOW_INTROSPECTION": "true",
    "BRAPI_CACHE_TTL_SECONDS": "0",
}


@pytest.fixture(autouse=True)
def isolate_test_env() -> Generator[None, None, None]:
    tracked_keys = set(TEST_ENV_OVERRIDES.keys()) | {"DATABASE_URL"}
    original_values = {key: os.environ.get(key) for key in tracked_keys}
    yield
    for key, value in original_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def app(tmp_path: Path):
    test_db_path = tmp_path / "test.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
    for key, value in TEST_ENV_OVERRIDES.items():
        os.environ[key] = value

    from app import create_app
    from app.extensions.database import db

    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        db.drop_all()
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def client(app) -> Generator:
    yield app.test_client()


@pytest.fixture(autouse=True)
def clear_investment_service_cache() -> Generator[None, None, None]:
    from app.extensions.integration_metrics import reset_metrics_for_tests
    from app.services.investment_service import InvestmentService
    from app.services.login_attempt_guard_service import (
        reset_login_attempt_guard_for_tests,
    )

    InvestmentService._clear_cache_for_tests()
    reset_metrics_for_tests()
    reset_login_attempt_guard_for_tests()
    yield
    InvestmentService._clear_cache_for_tests()
    reset_metrics_for_tests()
    reset_login_attempt_guard_for_tests()
