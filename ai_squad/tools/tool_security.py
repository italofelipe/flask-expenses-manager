"""
Security primitives for Auraxis AI Squad tools.

This module provides the foundational security layer that all agent tools
must use before performing write operations, subprocess calls, or git actions.

It is separated from project_tools.py so that:
1. Security logic is independently testable.
2. Any new tool automatically inherits the same constraints.
3. Audit logging is centralized and consistent.

Design Decisions:
- WRITABLE_DIRS uses an allowlist (deny-by-default) rather than a blocklist.
  This means new directories are NOT writable until explicitly added here.
- PROTECTED_FILES is a secondary denylist for files that live inside
  writable directories but must never be touched (e.g., migrations/__init__.py).
- Path validation uses Path.resolve() to neutralize symlinks and '../' traversal.
- All subprocess calls go through safe_subprocess() which enforces a timeout.
- audit_log() writes to ai_squad/logs/tool_audit.log for post-incident forensics.

Maintainer Notes:
- When adding a new writable directory, update WRITABLE_DIRS below.
- When adding a new protected file, update PROTECTED_FILES below.
- When adding a new git-unsafe pattern, update GIT_STAGE_BLOCKLIST below.
- This module must NOT import from project_tools.py (no circular deps).

References:
- .context/05_quality_and_gates.md — quality gates enforced by tools
- steering.md — execution governance and branching conventions
"""

import logging
from functools import wraps
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# PROJECT_ROOT — resolved once at import time.
# Path: ai_squad/tools/tool_security.py → ai_squad/tools → ai_squad → root
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# WRITABLE_DIRS — directories where agents are ALLOWED to write files.
# Everything outside this list is implicitly DENIED.
# ---------------------------------------------------------------------------
WRITABLE_DIRS: list[Path] = [
    PROJECT_ROOT / "app",
    PROJECT_ROOT / "tests",
    PROJECT_ROOT / "migrations",
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "ai_squad" / "logs",
]

# ---------------------------------------------------------------------------
# PROTECTED_FILES — files that must NEVER be written by an agent,
# even if they are inside a writable directory.
# ---------------------------------------------------------------------------
PROTECTED_FILES: list[Path] = [
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".env.dev",
    PROJECT_ROOT / ".env.prod",
    PROJECT_ROOT / "run.py",
    PROJECT_ROOT / "run_without_db.py",
    PROJECT_ROOT / "config" / "__init__.py",
    PROJECT_ROOT / "pyproject.toml",
    PROJECT_ROOT / "requirements.txt",
    PROJECT_ROOT / "requirements-dev.txt",
    PROJECT_ROOT / "docker-compose.yml",
    PROJECT_ROOT / "docker-compose.dev.yml",
    PROJECT_ROOT / "docker-compose.prod.yml",
    PROJECT_ROOT / "Dockerfile",
    PROJECT_ROOT / "Dockerfile.prod",
    PROJECT_ROOT / ".pre-commit-config.yaml",
    PROJECT_ROOT / ".gitignore",
    PROJECT_ROOT / ".gitleaks.toml",
    PROJECT_ROOT / "steering.md",
    PROJECT_ROOT / "product.md",
    PROJECT_ROOT / "CLAUDE.md",
]

# ---------------------------------------------------------------------------
# BLOCKED_EXTENSIONS — file extensions agents must NEVER write,
# regardless of directory.
# ---------------------------------------------------------------------------
BLOCKED_EXTENSIONS: set[str] = {".env", ".pem", ".key", ".secret", ".credentials"}

# ---------------------------------------------------------------------------
# GIT_STAGE_BLOCKLIST — glob patterns that git_operations must NEVER stage.
# Used by fnmatch to filter changed files before 'git add'.
# ---------------------------------------------------------------------------
GIT_STAGE_BLOCKLIST: list[str] = [
    ".env",
    ".env.dev",
    ".env.prod",
    "*.pem",
    "*.key",
    "*.secret",
    ".coverage",
    ".coverage*",
    "coverage.xml",
    "__pycache__",
    "__pycache__/*",
    ".mypy_cache",
    ".mypy_cache/*",
    ".pytest_cache",
    ".pytest_cache/*",
    "ai_squad/logs/*",
    "*.log",
]

# ---------------------------------------------------------------------------
# DEFAULT_TIMEOUT_SECONDS — maximum duration for any subprocess call.
# Individual tools may override this with shorter/longer values.
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT_SECONDS: int = 120

# ---------------------------------------------------------------------------
# CONVENTIONAL_BRANCH_PREFIXES — valid branch name prefixes.
# Enforces conventional branching as defined in steering.md.
# ---------------------------------------------------------------------------
CONVENTIONAL_BRANCH_PREFIXES: tuple[str, ...] = (
    "feat/",
    "fix/",
    "refactor/",
    "chore/",
    "docs/",
    "test/",
    "perf/",
    "security/",
)

# ---------------------------------------------------------------------------
# Audit Logger Setup
# ---------------------------------------------------------------------------
_LOG_DIR = PROJECT_ROOT / "ai_squad" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_audit_logger = logging.getLogger("auraxis.tool_audit")
if not _audit_logger.handlers:
    _handler = logging.FileHandler(_LOG_DIR / "tool_audit.log")
    _handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    _audit_logger.addHandler(_handler)
    _audit_logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# audit_log — structured logging for every tool invocation.
# ---------------------------------------------------------------------------
def audit_log(
    tool_name: str,
    args: dict,
    result: str,
    status: str = "OK",
) -> None:
    """
    Write a structured audit entry for a tool invocation.

    Args:
        tool_name: Name of the tool being invoked (e.g., 'write_file_content').
        args: Dictionary of arguments passed to the tool.
        result: String summary of the tool result (truncated to 200 chars).
        status: One of 'OK', 'ERROR', or 'BLOCKED'.

    Side Effects:
        Appends a line to ai_squad/logs/tool_audit.log.
    """
    _audit_logger.info(
        f"tool={tool_name} | status={status} | args={args} | "
        f"result_preview={str(result)[:200]}"
    )


# ---------------------------------------------------------------------------
# validate_write_path — path validation with allowlist enforcement.
# ---------------------------------------------------------------------------
def validate_write_path(raw_path: str) -> Path:
    """
    Validate that a file path is safe for agent write operations.

    Validation rules (applied in order):
    1. Resolve to absolute path (neutralizes '../', symlinks, '~').
    2. Must be inside PROJECT_ROOT.
    3. Must be inside one of WRITABLE_DIRS.
    4. Must NOT match any PROTECTED_FILES.
    5. Must NOT have a BLOCKED_EXTENSION.

    Args:
        raw_path: Relative or absolute path string from the agent.

    Returns:
        Resolved absolute Path on success.

    Raises:
        PermissionError: With descriptive message on any validation failure.

    Example:
        >>> validate_write_path("app/models/new_model.py")
        PosixPath('/path/to/project/app/models/new_model.py')

        >>> validate_write_path(".env")
        PermissionError: Path '.env' is not in any writable directory.
    """
    resolved = (PROJECT_ROOT / raw_path).resolve()

    # Rule 1: Must be inside project root (prevents escape)
    # Uses Path.is_relative_to() instead of str.startswith() to avoid
    # prefix collisions (e.g., /project-evil/ matching /project).
    if not resolved.is_relative_to(PROJECT_ROOT):
        raise PermissionError(f"Path escapes project root: {raw_path}")

    # Rule 2: Must be inside an allowed writable directory
    in_writable = any(resolved.is_relative_to(wd) for wd in WRITABLE_DIRS)
    if not in_writable:
        allowed = [str(d.relative_to(PROJECT_ROOT)) for d in WRITABLE_DIRS]
        raise PermissionError(
            f"Path '{raw_path}' is not in any writable directory. "
            f"Allowed directories: {allowed}"
        )

    # Rule 3: Not a protected file
    if resolved in PROTECTED_FILES:
        raise PermissionError(
            f"Path '{raw_path}' is a protected file and cannot be written."
        )

    # Rule 4: No blocked extension
    if resolved.suffix in BLOCKED_EXTENSIONS:
        raise PermissionError(
            f"Extension '{resolved.suffix}' is blocked for agent writes."
        )

    return resolved


# ---------------------------------------------------------------------------
# safe_subprocess — subprocess wrapper with enforced timeout.
# ---------------------------------------------------------------------------
def safe_subprocess(
    cmd: list[str],
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    cwd: Optional[str] = None,
) -> dict:
    """
    Run a subprocess with enforced timeout and output capture.

    This wrapper ensures that no tool can hang the agent process indefinitely.
    All subprocess calls in project_tools.py should use this function.

    Args:
        cmd: Command and arguments as a list of strings.
        timeout: Maximum execution time in seconds (default: 120).
        cwd: Working directory for the command (default: PROJECT_ROOT).

    Returns:
        Dictionary with keys:
        - 'stdout' (str): Standard output from the command.
        - 'stderr' (str): Standard error from the command.
        - 'returncode' (int): Process exit code (-1 if timed out).

    Example:
        >>> safe_subprocess(["git", "status"], timeout=10)
        {'stdout': 'On branch master...', 'stderr': '', 'returncode': 0}
    """
    import subprocess

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or str(PROJECT_ROOT),
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"TIMEOUT: command exceeded {timeout}s limit",
            "returncode": -1,
        }


# ---------------------------------------------------------------------------
# audited_tool — decorator for wrapping tools with automatic audit logging.
# ---------------------------------------------------------------------------
def audited_tool(tool_name: str):
    """
    Decorator that wraps any tool function with audit logging.

    Usage:
        @audited_tool("my_tool")
        def my_tool(arg1, arg2):
            ...

    This ensures that every invocation (success or failure) is recorded
    in the audit log with the tool name, arguments, and result.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            arg_repr = {"args": args, "kwargs": kwargs}
            try:
                result = func(*args, **kwargs)
                audit_log(tool_name, arg_repr, str(result), status="OK")
                return result
            except Exception as e:
                audit_log(tool_name, arg_repr, str(e), status="ERROR")
                raise

        return wrapper

    return decorator
