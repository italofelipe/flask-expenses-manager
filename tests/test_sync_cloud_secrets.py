from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import sync_cloud_secrets


def _completed_process(
    stdout: str, returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["aws"],
        returncode=returncode,
        stdout=stdout,
        stderr="error",
    )


def test_load_ssm_parameters_maps_path_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = """
    {
      "Parameters": [
        {"Name": "/auraxis/prod/SECRET_KEY", "Value": "sk"},
        {"Name": "/auraxis/prod/JWT_SECRET_KEY", "Value": "jwt"}
      ]
    }
    """.strip()

    monkeypatch.setattr(
        sync_cloud_secrets.subprocess,
        "run",
        lambda *args, **kwargs: _completed_process(payload),
    )

    values = sync_cloud_secrets.load_ssm_parameters("/auraxis/prod", "us-east-1")
    assert values["SECRET_KEY"] == "sk"
    assert values["JWT_SECRET_KEY"] == "jwt"


def test_load_secrets_manager_reads_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = """
    {"SecretString":"{\\"SECRET_KEY\\":\\"sk\\",\\"DB_HOST\\":\\"db\\"}"}
    """.strip()

    monkeypatch.setattr(
        sync_cloud_secrets.subprocess,
        "run",
        lambda *args, **kwargs: _completed_process(payload),
    )

    values = sync_cloud_secrets.load_secrets_manager("auraxis/prod/app", "us-east-1")
    assert values["SECRET_KEY"] == "sk"
    assert values["DB_HOST"] == "db"


def test_write_env_file_escapes_unsafe_values(tmp_path: Path) -> None:
    output = tmp_path / ".env.runtime"
    sync_cloud_secrets.write_env_file(
        output,
        {
            "SECRET_KEY": "abc 123",
            "DB_HOST": "db",
        },
    )

    content = output.read_text(encoding="utf-8")
    assert "DB_HOST=db" in content
    assert "SECRET_KEY='abc 123'" in content


def test_validate_required_keys_raises_when_missing() -> None:
    with pytest.raises(
        sync_cloud_secrets.SecretSyncError, match="Missing required keys"
    ):
        sync_cloud_secrets._validate_required_keys(
            {"SECRET_KEY": "sk"},
            {"SECRET_KEY", "JWT_SECRET_KEY"},
        )
