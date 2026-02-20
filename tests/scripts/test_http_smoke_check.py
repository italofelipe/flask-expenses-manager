from __future__ import annotations

import importlib.util
import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import ModuleType


def _load_smoke_module() -> ModuleType:
    module_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "http_smoke_check.py"
    )
    spec = importlib.util.spec_from_file_location("http_smoke_check", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load scripts/http_smoke_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_request_json_preserves_post_on_redirect() -> None:
    smoke = _load_smoke_module()
    received_methods: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/graphql":
                self.send_response(301)
                self.send_header("Location", "/graphql-target")
                self.end_headers()
                return

            if self.path == "/graphql-target":
                received_methods.append("POST")
                length = int(self.headers.get("Content-Length", "0"))
                _ = self.rfile.read(length)
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "errors": [
                                {
                                    "message": "Validation failed",
                                    "extensions": {"code": "VALIDATION_ERROR"},
                                }
                            ]
                        }
                    ).encode("utf-8")
                )
                return

            self.send_response(404)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/graphql-target":
                received_methods.append("GET")
                self.send_response(405)
                self.end_headers()
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    port = _free_port()
    server = HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = smoke._request_json(  # type: ignore[attr-defined]
            method="POST",
            url=f"http://127.0.0.1:{port}/graphql",
            payload={"query": "   "},
            timeout=5,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 400
    assert received_methods == ["POST"]
