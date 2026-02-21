"""
Unit tests for ai_squad/tools/tool_security.py.

These tests validate the security boundaries that protect the Auraxis project
from unintended file writes, path traversal, and unsafe git operations.

Test Strategy:
- Each test validates a single security rule in isolation.
- Tests use validate_write_path() directly (no CrewAI/LangChain dependency).
- Positive tests confirm that legitimate paths are accepted.
- Negative tests confirm that dangerous paths raise PermissionError.

References:
- ai_squad/tools/tool_security.py — module under test
- .context/05_quality_and_gates.md — testing requirements

Note:
- sys.path setup is handled by conftest.py in this directory.
"""

import pytest
from tools.tool_security import (
    BLOCKED_EXTENSIONS,
    CONVENTIONAL_BRANCH_PREFIXES,
    GIT_STAGE_BLOCKLIST,
    PROJECT_ROOT,
    PROTECTED_FILES,
    WRITABLE_DIRS,
    validate_write_path,
)


class TestProjectRoot:
    """Verify that PROJECT_ROOT resolves to the actual project directory."""

    def test_project_root_exists(self) -> None:
        assert PROJECT_ROOT.exists(), f"PROJECT_ROOT does not exist: {PROJECT_ROOT}"

    def test_project_root_contains_tasks(self) -> None:
        assert (
            PROJECT_ROOT / "TASKS.md"
        ).exists(), "TASKS.md not found at PROJECT_ROOT"

    def test_project_root_contains_app(self) -> None:
        assert (
            PROJECT_ROOT / "app"
        ).is_dir(), "app/ directory not found at PROJECT_ROOT"


class TestValidateWritePath:
    """Validate the path allowlist/denylist logic."""

    # --- Positive cases: paths that SHOULD be accepted ---

    def test_allows_app_directory(self) -> None:
        """Files inside app/ are writable."""
        path = validate_write_path("app/models/new_model.py")
        assert path.is_relative_to(PROJECT_ROOT / "app")

    def test_allows_tests_directory(self) -> None:
        """Files inside tests/ are writable."""
        path = validate_write_path("tests/test_new_feature.py")
        assert path.is_relative_to(PROJECT_ROOT / "tests")

    def test_allows_migrations_directory(self) -> None:
        """Files inside migrations/ are writable."""
        path = validate_write_path("migrations/versions/new_migration.py")
        assert path.is_relative_to(PROJECT_ROOT / "migrations")

    def test_allows_docs_directory(self) -> None:
        """Files inside docs/ are writable."""
        path = validate_write_path("docs/new_runbook.md")
        assert path.is_relative_to(PROJECT_ROOT / "docs")

    def test_allows_nested_app_path(self) -> None:
        """Deeply nested paths inside app/ are accepted."""
        path = validate_write_path("app/application/services/new_service.py")
        assert path.is_relative_to(PROJECT_ROOT / "app")

    # --- Negative cases: paths that MUST be rejected ---

    def test_blocks_env_file(self) -> None:
        """Writing to .env at root must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path(".env")

    def test_blocks_env_dev_file(self) -> None:
        """Writing to .env.dev must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path(".env.dev")

    def test_blocks_run_py(self) -> None:
        """Writing to run.py must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path("run.py")

    def test_blocks_path_traversal(self) -> None:
        """Path traversal via ../ must be blocked."""
        with pytest.raises(PermissionError):
            validate_write_path("../../etc/passwd")

    def test_blocks_env_extension_in_writable_dir(self) -> None:
        """Even inside app/, .env extension is blocked."""
        with pytest.raises(PermissionError, match="blocked for agent writes"):
            validate_write_path("app/secrets.env")

    def test_blocks_pem_extension_in_writable_dir(self) -> None:
        """Even inside app/, .pem extension is blocked."""
        with pytest.raises(PermissionError, match="blocked for agent writes"):
            validate_write_path("app/server.pem")

    def test_blocks_key_extension_in_writable_dir(self) -> None:
        """Even inside tests/, .key extension is blocked."""
        with pytest.raises(PermissionError, match="blocked for agent writes"):
            validate_write_path("tests/private.key")

    def test_blocks_root_level_write(self) -> None:
        """Writing to pyproject.toml must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path("pyproject.toml")

    def test_blocks_config_directory(self) -> None:
        """Writing to config/ must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path("config/__init__.py")

    def test_blocks_dockerfile(self) -> None:
        """Writing to Dockerfile must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path("Dockerfile")

    def test_blocks_gitignore(self) -> None:
        """Writing to .gitignore must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path(".gitignore")

    def test_blocks_steering_md(self) -> None:
        """Writing to steering.md must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path("steering.md")

    def test_blocks_product_md(self) -> None:
        """Writing to product.md must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path("product.md")

    def test_blocks_ai_squad_main(self) -> None:
        """Writing to ai_squad/main.py must be blocked."""
        with pytest.raises(PermissionError, match="not in any writable directory"):
            validate_write_path("ai_squad/main.py")


class TestSecurityConstants:
    """Verify that security constants are properly configured."""

    def test_writable_dirs_inside_project_root(self) -> None:
        """All WRITABLE_DIRS should be inside PROJECT_ROOT."""
        for wd in WRITABLE_DIRS:
            assert wd.is_relative_to(PROJECT_ROOT), f"{wd} escapes PROJECT_ROOT"

    def test_protected_files_are_absolute(self) -> None:
        """All PROTECTED_FILES should be absolute paths."""
        for pf in PROTECTED_FILES:
            assert pf.is_absolute(), f"{pf} is not absolute"

    def test_blocked_extensions_start_with_dot(self) -> None:
        """All BLOCKED_EXTENSIONS should start with a dot."""
        for ext in BLOCKED_EXTENSIONS:
            assert ext.startswith("."), f"Extension '{ext}' must start with '.'"

    def test_branch_prefixes_end_with_slash(self) -> None:
        """All CONVENTIONAL_BRANCH_PREFIXES should end with '/'."""
        for prefix in CONVENTIONAL_BRANCH_PREFIXES:
            assert prefix.endswith("/"), f"Prefix '{prefix}' must end with '/'"

    def test_git_blocklist_has_env_patterns(self) -> None:
        """GIT_STAGE_BLOCKLIST must include .env patterns."""
        env_patterns = [p for p in GIT_STAGE_BLOCKLIST if ".env" in p]
        assert len(env_patterns) >= 1, "GIT_STAGE_BLOCKLIST must block .env files"

    def test_git_blocklist_has_pem_pattern(self) -> None:
        """GIT_STAGE_BLOCKLIST must include *.pem pattern."""
        assert (
            "*.pem" in GIT_STAGE_BLOCKLIST
        ), "GIT_STAGE_BLOCKLIST must block .pem files"
