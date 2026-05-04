# ruff: noqa: E501
"""GET /graphql/playground — embedded GraphiQL interface.

Available only when the ``ENABLE_GRAPHQL_PLAYGROUND`` feature flag is enabled.
Requires an authenticated request with the ``admin`` role.  Default: disabled.

Intended for dev/staging only.  Do NOT enable in production.
"""

from __future__ import annotations

from flask import Response, make_response, request

from app.auth import get_active_auth_context
from app.controllers.response_contract import compat_error_response
from app.utils.feature_flags import is_feature_enabled

_FLAG_KEY = "ENABLE_GRAPHQL_PLAYGROUND"

_GRAPHIQL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GraphiQL — Auraxis API</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/graphiql@3/graphiql.min.css" />
  <style>
    html, body, #graphiql {{ height: 100%; margin: 0; overflow: hidden; }}
  </style>
</head>
<body>
  <div id="graphiql">Loading GraphiQL…</div>
  <script
    crossorigin
    src="https://cdn.jsdelivr.net/npm/react@18/umd/react.production.min.js"
  ></script>
  <script
    crossorigin
    src="https://cdn.jsdelivr.net/npm/react-dom@18/umd/react-dom.production.min.js"
  ></script>
  <script
    crossorigin
    src="https://cdn.jsdelivr.net/npm/graphiql@3/graphiql.min.js"
  ></script>
  <script>
    const fetchURL = "{graphql_url}";
    const fetcher = GraphiQL.createFetcher({{ url: fetchURL }});
    ReactDOM.render(
      React.createElement(GraphiQL, {{ fetcher: fetcher }}),
      document.getElementById("graphiql")
    );
  </script>
</body>
</html>
"""


def _is_admin() -> bool:
    try:
        ctx = get_active_auth_context()
        return "admin" in ctx.roles
    except Exception:
        return False


def _not_found_response() -> Response:
    return compat_error_response(
        legacy_payload={"message": "Not Found", "success": False},
        status_code=404,
        message="Not Found",
        error_code="NOT_FOUND",
    )


def _forbidden_response() -> Response:
    return compat_error_response(
        legacy_payload={"message": "Forbidden", "success": False},
        status_code=403,
        message="Forbidden",
        error_code="FORBIDDEN",
    )


def graphql_playground() -> Response:
    """Serve embedded GraphiQL when the feature flag is on and caller is admin."""
    if not is_feature_enabled(_FLAG_KEY):
        return _not_found_response()

    auth_header = str(request.headers.get("Authorization", "")).strip()
    if not auth_header.startswith("Bearer "):
        return _forbidden_response()

    if not _is_admin():
        return _forbidden_response()

    graphql_url = request.host_url.rstrip("/") + "/graphql"
    html = _GRAPHIQL_HTML.format(graphql_url=graphql_url)
    response = make_response(html)
    response.content_type = "text/html; charset=utf-8"
    return response
