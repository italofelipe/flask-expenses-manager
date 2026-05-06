"""S3-backed avatar upload/delete service."""

from __future__ import annotations

import uuid
from typing import IO, Any

from flask import current_app

_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class AvatarStorageError(RuntimeError):
    pass


class AvatarValidationError(ValueError):
    pass


def _get_s3_client() -> Any:
    import boto3

    region = current_app.config.get("AVATAR_S3_REGION", "us-east-1")
    return boto3.client("s3", region_name=region)


def _bucket() -> str:
    bucket: str = current_app.config.get("AVATAR_S3_BUCKET", "")
    if not bucket:
        raise AvatarStorageError("AVATAR_S3_BUCKET is not configured.")
    return bucket


def _object_key(user_id: str, ext: str) -> str:
    return f"avatars/{user_id}/{uuid.uuid4().hex}.{ext}"


def _cdn_url(key: str) -> str:
    base = current_app.config.get("AVATAR_CDN_BASE_URL", "").rstrip("/")
    if base:
        return f"{base}/{key}"
    region = current_app.config.get("AVATAR_S3_REGION", "us-east-1")
    bucket = _bucket()
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def validate_avatar_file(
    file_stream: IO[bytes],
    content_type: str,
    filename: str,
) -> str:
    """Validate and return the normalised file extension."""
    if content_type not in _ALLOWED_MIME_TYPES:
        raise AvatarValidationError(
            f"Tipo de arquivo não permitido: {content_type}. Use JPEG, PNG ou WebP."
        )
    ext = (filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise AvatarValidationError(
            f"Extensão não permitida: {ext}. Use jpg, png ou webp."
        )
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    if size > _MAX_SIZE_BYTES:
        raise AvatarValidationError(
            f"Arquivo muito grande ({size // 1024} KB). Máximo: 5 MB."
        )
    return ext


def upload_avatar(
    user_id: str,
    file_stream: IO[bytes],
    content_type: str,
    ext: str,
) -> str:
    """Upload avatar to S3 and return the public URL."""
    key = _object_key(user_id, ext)
    bucket = _bucket()
    try:
        s3 = _get_s3_client()
        s3.upload_fileobj(
            file_stream,
            bucket,
            key,
            ExtraArgs={"ContentType": content_type, "ACL": "public-read"},
        )
    except Exception as exc:
        raise AvatarStorageError(f"Falha ao fazer upload do avatar: {exc}") from exc
    return _cdn_url(key)


def delete_avatar_by_url(avatar_url: str) -> None:
    """Delete the S3 object for the given public URL (best-effort)."""
    try:
        base = current_app.config.get("AVATAR_CDN_BASE_URL", "").rstrip("/")
        bucket = _bucket()
        if base and avatar_url.startswith(base + "/"):
            key = avatar_url[len(base) + 1 :]
        else:
            region = current_app.config.get("AVATAR_S3_REGION", "us-east-1")
            prefix = f"https://{bucket}.s3.{region}.amazonaws.com/"
            if not avatar_url.startswith(prefix):
                return
            key = avatar_url[len(prefix) :]
        s3 = _get_s3_client()
        s3.delete_object(Bucket=bucket, Key=key)
    except Exception:
        current_app.logger.warning(
            "event=avatar.delete_failed url=%s", avatar_url, exc_info=True
        )
