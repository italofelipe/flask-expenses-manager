import os
import sys
from pathlib import Path
from typing import Any, Generator

import pytest
from sqlalchemy.orm import close_all_sessions

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

TEST_ENV_OVERRIDES = {
    "SECRET_KEY": "test-secret-key-with-64-chars-minimum-for-jwt-signing-0001",
    "JWT_SECRET_KEY": "test-jwt-secret-key-with-64-chars-minimum-for-signing-0002",
    "BILLING_WEBHOOK_ALLOW_UNSIGNED": "true",
    "FLASK_DEBUG": "False",
    "FLASK_TESTING": "true",
    "SECURITY_ENFORCE_STRONG_SECRETS": "false",
    "DOCS_EXPOSURE_POLICY": "public",
    "CORS_ALLOWED_ORIGINS": "https://frontend.local",
    "GRAPHQL_ALLOW_INTROSPECTION": "true",
    "BRAPI_CACHE_TTL_SECONDS": "0",
}

for key, value in TEST_ENV_OVERRIDES.items():
    os.environ.setdefault(key, value)


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
    app.config["SECRET_KEY"] = TEST_ENV_OVERRIDES["SECRET_KEY"]
    app.config["JWT_SECRET_KEY"] = TEST_ENV_OVERRIDES["JWT_SECRET_KEY"]

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
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clear_investment_service_cache() -> Generator[None, None, None]:
    from app.extensions.brapi_cache import reset_brapi_cache_for_tests
    from app.extensions.integration_metrics import reset_metrics_for_tests
    from app.services.login_attempt_guard_service import (
        reset_login_attempt_guard_for_tests,
    )

    reset_brapi_cache_for_tests()
    reset_metrics_for_tests()
    reset_login_attempt_guard_for_tests()
    yield
    reset_brapi_cache_for_tests()
    reset_metrics_for_tests()
    reset_login_attempt_guard_for_tests()


@pytest.fixture(autouse=True)
def cleanup_sqlalchemy_sessions() -> Generator[None, None, None]:
    yield
    close_all_sessions()


@pytest.fixture
def query_counter(app: Any) -> Generator[dict[str, int], None, None]:
    """SQLAlchemy query counter fixture.

    Attaches an event listener to the engine that increments a counter for
    every SQL statement executed.  Yields a dict with key ``"n"`` so tests
    can assert ``counts["n"] <= threshold``.

    Usage::

        def test_foo(app, query_counter):
            with app.app_context():
                query_counter["n"] = 0  # reset if needed
                do_something()
                assert query_counter["n"] <= 5
    """
    from sqlalchemy import event

    from app.extensions.database import db

    counts: dict[str, int] = {"n": 0}

    def _before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: Any,
        parameters: Any,
        context: Any,
        executemany: Any,
    ) -> None:
        counts["n"] += 1

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", _before_cursor_execute)

    yield counts

    with app.app_context():
        event.remove(db.engine, "before_cursor_execute", _before_cursor_execute)
