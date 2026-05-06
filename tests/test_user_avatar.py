"""Tests for POST/DELETE /user/me/avatar (#1126)."""

from __future__ import annotations

import io
import uuid
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from flask.testing import FlaskClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client: FlaskClient, prefix: str = "avatar") -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    password = "StrongPass@123"
    r = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert r.status_code == 201
    r2 = client.post("/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r2.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _jpeg_bytes(size: int = 1024) -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * (size - 4)


def _upload(
    client: FlaskClient,
    token: str,
    *,
    data: bytes = b"",
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
) -> object:
    return client.post(
        "/user/me/avatar",
        data={"file": (io.BytesIO(data or _jpeg_bytes()), filename)},
        content_type="multipart/form-data",
        headers=_auth(token),
    )


@pytest.fixture()
def mock_s3() -> Generator[MagicMock, None, None]:
    fake_client = MagicMock()
    fake_client.upload_fileobj.return_value = None
    fake_client.delete_object.return_value = None
    with (
        patch("app.services.avatar_storage._get_s3_client", return_value=fake_client),
        patch("app.services.avatar_storage._bucket", return_value="test-bucket"),
    ):
        yield fake_client


# ---------------------------------------------------------------------------
# POST /user/me/avatar
# ---------------------------------------------------------------------------


class TestAvatarUpload:
    def test_upload_returns_avatar_url(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        res = _upload(client, token)
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert "avatar_url" in body["data"]
        assert body["data"]["avatar_url"].startswith("https://")

    def test_upload_persists_in_profile(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        _upload(client, token)
        res = client.get("/user/profile", headers=_auth(token))
        assert res.status_code == 200
        body = res.get_json()
        avatar = body["data"]["user"]["avatar_url"]
        assert avatar is not None and avatar.startswith("https://")

    def test_upload_replaces_old_avatar(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        _upload(client, token)
        _upload(client, token)
        # S3 delete should have been called for the old avatar on second upload
        assert mock_s3.delete_object.call_count >= 1

    def test_upload_requires_auth(self, client: FlaskClient) -> None:
        res = client.post(
            "/user/me/avatar",
            data={"file": (io.BytesIO(_jpeg_bytes()), "photo.jpg")},
            content_type="multipart/form-data",
        )
        assert res.status_code in {401, 422}

    def test_upload_missing_file_field_returns_400(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        res = client.post(
            "/user/me/avatar",
            data={},
            content_type="multipart/form-data",
            headers=_auth(token),
        )
        assert res.status_code == 400
        assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_upload_invalid_mime_type_returns_400(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        res = _upload(
            client,
            token,
            data=b"GIF89a",
            filename="anim.gif",
            content_type="image/gif",
        )
        assert res.status_code == 400
        assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_upload_file_too_large_returns_400(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        big = _jpeg_bytes(6 * 1024 * 1024)  # 6 MB
        res = _upload(client, token, data=big)
        assert res.status_code == 400
        assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_s3_failure_returns_500(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        mock_s3.upload_fileobj.side_effect = Exception("S3 unavailable")
        res = _upload(client, token)
        assert res.status_code == 500
        assert res.get_json()["error"]["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# DELETE /user/me/avatar
# ---------------------------------------------------------------------------


class TestAvatarDelete:
    def test_delete_removes_avatar(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        _upload(client, token)
        res = client.delete("/user/me/avatar", headers=_auth(token))
        assert res.status_code == 200
        assert res.get_json()["success"] is True

        profile = client.get("/user/profile", headers=_auth(token)).get_json()
        assert profile["data"]["user"]["avatar_url"] is None

    def test_delete_calls_s3_delete(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        _upload(client, token)
        client.delete("/user/me/avatar", headers=_auth(token))
        assert mock_s3.delete_object.called

    def test_delete_no_avatar_returns_404(
        self, client: FlaskClient, mock_s3: MagicMock
    ) -> None:
        token = _register_and_login(client)
        res = client.delete("/user/me/avatar", headers=_auth(token))
        assert res.status_code == 404
        assert res.get_json()["error"]["code"] == "NOT_FOUND"

    def test_delete_requires_auth(self, client: FlaskClient) -> None:
        res = client.delete("/user/me/avatar")
        assert res.status_code in {401, 422}
