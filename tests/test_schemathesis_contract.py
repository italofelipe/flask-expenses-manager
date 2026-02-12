from __future__ import annotations

import os

import pytest
import schemathesis
from hypothesis import HealthCheck, settings

from app import create_app

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/auraxis_schemathesis.sqlite3")
os.environ.setdefault("SECRET_KEY", "x" * 64)
os.environ.setdefault("JWT_SECRET_KEY", "y" * 64)
os.environ.setdefault("FLASK_DEBUG", "False")
os.environ.setdefault("FLASK_TESTING", "true")
os.environ.setdefault("SECURITY_ENFORCE_STRONG_SECRETS", "false")
os.environ.setdefault("DOCS_EXPOSURE_POLICY", "public")

_APP = create_app()


@pytest.fixture(scope="session", autouse=True)
def _dispose_schemathesis_app() -> None:
    yield
    from app.extensions.database import db

    with _APP.app_context():
        db.session.remove()
        db.engine.dispose()


def _normalize_parameter(parameter: object) -> dict[str, object] | None:
    if not isinstance(parameter, dict):
        return None
    if str(parameter.get("in", "")).lower() == "body":
        return None
    if "schema" in parameter or "type" not in parameter:
        return parameter
    parameter["schema"] = {"type": str(parameter.pop("type"))}
    return parameter


def _normalize_operation_parameters(operation: dict[str, object]) -> None:
    parameters = operation.get("parameters")
    if not isinstance(parameters, list):
        return
    normalized_parameters = []
    for parameter in parameters:
        normalized_parameter = _normalize_parameter(parameter)
        if normalized_parameter is not None:
            normalized_parameters.append(normalized_parameter)
    operation["parameters"] = normalized_parameters


def _load_normalized_openapi_spec() -> dict[str, object]:
    response = _APP.test_client().get("/docs/swagger/")
    spec = dict(response.get_json() or {})
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return spec

    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            _normalize_operation_parameters(operation)
    return spec


_NORMALIZED_SPEC = _load_normalized_openapi_spec()
_RAW_SCHEMA = schemathesis.openapi.from_dict(_NORMALIZED_SPEC, app=_APP)
SCHEMA = _RAW_SCHEMA.include(
    path_regex=(
        r"^/auth/(login|register)$|^/transactions/list$|^/transactions/summary$|"
        r"^/transactions/expenses$"
    )
)

pytestmark = pytest.mark.schemathesis
SERVER_ERROR_CHECK = getattr(
    schemathesis.checks,
    "not_a_server_error",
    getattr(schemathesis.checks, "no_server_errors", None),
)


@SCHEMA.parametrize()
@settings(
    max_examples=int(os.getenv("SCHEMATHESIS_MAX_EXAMPLES", "5")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_openapi_contract_no_server_errors(case: schemathesis.Case) -> None:
    assert SERVER_ERROR_CHECK is not None
    response = case.call(headers={"X-API-Contract": "v2"})
    case.validate_response(
        response,
        checks=(SERVER_ERROR_CHECK,),
    )
