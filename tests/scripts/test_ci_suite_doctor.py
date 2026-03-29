from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "ci_suite_doctor.py"
    spec = importlib.util.spec_from_file_location("ci_suite_doctor", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_report_marks_missing_image_and_env(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    compose_file = tmp_path / "docker-compose.ci.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    env_file = tmp_path / ".env"

    monkeypatch.setattr(module.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(args):
        joined = " ".join(args)
        if joined == "docker compose version":

            class Result:
                returncode = 0
                stdout = "Docker Compose version v2.0.0"
                stderr = ""

            return Result()

        class Result:
            returncode = 1
            stdout = ""
            stderr = "missing"

        return Result()

    monkeypatch.setattr(module, "_run", fake_run)

    report = module._build_report(
        compose_file=compose_file,
        env_file=env_file,
        web_image="auraxis-ci-dev:test",
    )

    assert report.status == "failed"
    checks = {check.name: check for check in report.checks}
    assert checks["env:file"].success is False
    assert checks["docker:image"].success is False


def test_main_writes_report_and_summary(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    compose_file = tmp_path / "docker-compose.ci.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_DB=test\n", encoding="utf-8")
    report_path = tmp_path / "reports" / "doctor.json"
    summary_path = tmp_path / "reports" / "doctor.md"

    monkeypatch.setattr(module.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(args):
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_suite_doctor.py",
            "--compose-file",
            str(compose_file),
            "--env-file",
            str(env_file),
            "--web-image",
            "auraxis-ci-dev:test",
            "--report-path",
            str(report_path),
            "--summary-path",
            str(summary_path),
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert "CI suite doctor" in summary_path.read_text(encoding="utf-8")
