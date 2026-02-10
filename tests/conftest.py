import os
import sys
from pathlib import Path
from typing import Generator

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture
def app(tmp_path: Path):
    test_db_path = tmp_path / "test.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"
    os.environ["FLASK_DEBUG"] = "False"
    os.environ["BRAPI_CACHE_TTL_SECONDS"] = "0"

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


@pytest.fixture
def client(app) -> Generator:
    yield app.test_client()


@pytest.fixture(autouse=True)
def clear_investment_service_cache() -> Generator[None, None, None]:
    from app.services.investment_service import InvestmentService

    InvestmentService._clear_cache_for_tests()
    yield
    InvestmentService._clear_cache_for_tests()
