"""
Auraxis AI Squad — CrewAI Tools (BaseTool).

All tools use the security primitives from tool_security.py:
- validate_write_path() for file writes
- safe_subprocess() for subprocess calls
- audit_log() for structured audit logging

References:
- ai_squad/tools/tool_security.py — security module
- ai_squad/AGENT_ARCHITECTURE.md — tools registry
- .context/05_quality_and_gates.md — quality gates
"""

import fnmatch

from crewai.tools import BaseTool

from .tool_security import (
    CONVENTIONAL_BRANCH_PREFIXES,
    GIT_STAGE_BLOCKLIST,
    PROJECT_ROOT,
    audit_log,
    safe_subprocess,
    validate_write_path,
)

# ---------------------------------------------------------------------------
# GOVERNANCE_ALLOWLIST — files that read_governance_file can access.
# ---------------------------------------------------------------------------
GOVERNANCE_ALLOWLIST: list[str] = ["product.md", "steering.md"]

# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------


class ReadTasksTool(BaseTool):
    name: str = "read_tasks"
    description: str = (
        "Reads TASKS.md to understand current project status, "
        "backlog, and priorities."
    )

    def _run(self, query: str = None) -> str:
        path = PROJECT_ROOT / "TASKS.md"
        audit_log("read_tasks", {"path": str(path)}, "reading", status="OK")
        if not path.exists():
            return f"Error: TASKS.md not found at {path}"
        return path.read_text(encoding="utf-8")


class ReadSchemaTool(BaseTool):
    name: str = "read_schema"
    description: str = "Reads schema.graphql to understand GraphQL API contracts."

    def _run(self, query: str = None) -> str:
        path = PROJECT_ROOT / "schema.graphql"
        audit_log("read_schema", {"path": str(path)}, "reading", status="OK")
        if not path.exists():
            return f"Error: schema.graphql not found at {path}"
        return path.read_text(encoding="utf-8")


class ReadContextFileTool(BaseTool):
    name: str = "read_context_file"
    description: str = (
        "Reads a file from the .context/ knowledge base. "
        "Provide the filename relative to .context/ "
        "(e.g., 'README.md', '04_architecture_snapshot.md')."
    )

    def _run(self, filename: str) -> str:
        context_dir = PROJECT_ROOT / ".context"
        resolved = (context_dir / filename).resolve()

        # Anti-escape: must stay inside .context/
        if not resolved.is_relative_to(context_dir):
            msg = f"BLOCKED: '{filename}' escapes .context/ directory."
            audit_log(
                "read_context_file",
                {"filename": filename},
                msg,
                status="BLOCKED",
            )
            return msg

        audit_log(
            "read_context_file",
            {"filename": filename},
            "reading",
            status="OK",
        )
        if not resolved.exists():
            return f"Error: File not found: .context/{filename}"
        return resolved.read_text(encoding="utf-8")


class ReadGovernanceFileTool(BaseTool):
    name: str = "read_governance_file"
    description: str = (
        "Reads a governance file (product.md or steering.md) " "from the project root."
    )

    def _run(self, filename: str) -> str:
        if filename not in GOVERNANCE_ALLOWLIST:
            msg = (
                f"BLOCKED: '{filename}' is not a governance file. "
                f"Allowed: {GOVERNANCE_ALLOWLIST}"
            )
            audit_log(
                "read_governance_file",
                {"filename": filename},
                msg,
                status="BLOCKED",
            )
            return msg

        path = PROJECT_ROOT / filename
        audit_log(
            "read_governance_file",
            {"filename": filename},
            "reading",
            status="OK",
        )
        if not path.exists():
            return f"Error: {filename} not found at project root."
        return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Execution tools
# ---------------------------------------------------------------------------


class RunTestsTool(BaseTool):
    name: str = "run_backend_tests"
    description: str = (
        "Runs the pytest test suite with timeout protection. "
        "Returns stdout and stderr."
    )

    def _run(self, query: str = None) -> str:
        pytest_path = str(PROJECT_ROOT / ".venv" / "bin" / "pytest")
        import os

        if not os.path.exists(pytest_path):
            pytest_path = "pytest"

        result = safe_subprocess(
            [pytest_path, "--tb=short", "-q"],
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        output = f"STDOUT: {result['stdout']}\nSTDERR: {result['stderr']}"
        audit_log(
            "run_backend_tests",
            {"pytest_path": pytest_path},
            output[:200],
            status="OK" if result["returncode"] == 0 else "ERROR",
        )
        return output


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


class WriteFileTool(BaseTool):
    name: str = "write_file_content"
    description: str = (
        "Writes content to a file. Path must be relative to project root. "
        "Enforces security: only writable dirs, no protected files, "
        "no blocked extensions."
    )

    def _run(self, path: str, content: str) -> str:
        try:
            validated = validate_write_path(path)
        except PermissionError as e:
            msg = f"BLOCKED: {e}"
            audit_log(
                "write_file_content",
                {"path": path},
                msg,
                status="BLOCKED",
            )
            return msg

        validated.parent.mkdir(parents=True, exist_ok=True)
        validated.write_text(content, encoding="utf-8")

        msg = f"File {path} written successfully."
        audit_log(
            "write_file_content",
            {"path": path, "size": len(content)},
            msg,
            status="OK",
        )
        return msg


# ---------------------------------------------------------------------------
# Infrastructure tools
# ---------------------------------------------------------------------------


class AWSStatusTool(BaseTool):
    name: str = "check_aws_status"
    description: str = "Checks basic AWS EC2 infrastructure status (read-only)."

    def _run(self, query: str = None) -> str:
        result = safe_subprocess(
            [
                "aws",
                "ec2",
                "describe-instances",
                "--query",
                "Reservations[*].Instances[*]."
                "[InstanceId,State.Name,PublicIpAddress]",
            ],
            timeout=30,
        )
        output = f"AWS Status: {result['stdout']}"
        audit_log(
            "check_aws_status",
            {},
            output[:200],
            status="OK" if result["returncode"] == 0 else "ERROR",
        )
        return output


# ---------------------------------------------------------------------------
# Git tools — extracted helpers to keep cyclomatic complexity low.
# ---------------------------------------------------------------------------


def _git_create_branch(branch_name: str) -> str:
    """Create a branch with conventional prefix validation."""
    if not branch_name:
        return "Error: branch_name is required."

    if not branch_name.startswith(CONVENTIONAL_BRANCH_PREFIXES):
        allowed = ", ".join(CONVENTIONAL_BRANCH_PREFIXES)
        return (
            f"BLOCKED: Branch '{branch_name}' does not use a conventional "
            f"prefix. Allowed prefixes: {allowed}"
        )

    result = safe_subprocess(["git", "checkout", "-b", branch_name], timeout=15)
    if result["returncode"] != 0:
        return f"Error creating branch: {result['stderr']}"
    return f"Branch '{branch_name}' created."


def _git_collect_changed_files() -> list[str]:
    """Get list of changed files (staged + unstaged + untracked)."""
    # Staged and modified
    diff_result = safe_subprocess(["git", "diff", "--name-only", "HEAD"], timeout=15)
    # Untracked
    untracked_result = safe_subprocess(
        ["git", "ls-files", "--others", "--exclude-standard"], timeout=15
    )

    files: list[str] = []
    for output in [diff_result["stdout"], untracked_result["stdout"]]:
        files.extend(line.strip() for line in output.splitlines() if line.strip())
    return list(set(files))


def _git_filter_safe_files(files: list[str]) -> list[str]:
    """Filter files against GIT_STAGE_BLOCKLIST using fnmatch."""
    safe_files: list[str] = []
    for f in files:
        blocked = any(fnmatch.fnmatch(f, pattern) for pattern in GIT_STAGE_BLOCKLIST)
        if not blocked:
            safe_files.append(f)
    return safe_files


def _git_commit(message: str) -> str:
    """Selective staging + commit. Never uses 'git add .'."""
    # Detect current branch — block commits to master/main
    branch_result = safe_subprocess(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=10
    )
    current_branch = branch_result["stdout"].strip()
    if current_branch in ("master", "main"):
        return (
            "BLOCKED: Direct commits to 'master'/'main' are not allowed. "
            "Create a feature branch first."
        )

    if not message:
        return "Error: commit message is required."

    changed = _git_collect_changed_files()
    if not changed:
        return "Nothing to commit — no changed files detected."

    safe = _git_filter_safe_files(changed)
    if not safe:
        blocked_count = len(changed)
        return (
            f"Nothing to commit — all {blocked_count} changed file(s) "
            f"are in GIT_STAGE_BLOCKLIST."
        )

    # Selective staging (never 'git add .')
    safe_subprocess(["git", "add"] + safe, timeout=30)

    # Commit
    result = safe_subprocess(["git", "commit", "-m", message], timeout=30)
    if result["returncode"] != 0:
        return f"Commit error: {result['stderr']}"

    return f"Committed {len(safe)} file(s): {message}\n" f"Staged: {safe}"


def _git_status() -> str:
    """Return git status output."""
    result = safe_subprocess(["git", "status"], timeout=15)
    return result["stdout"]


class GitOpsTool(BaseTool):
    name: str = "git_operations"
    description: str = (
        "Git operations: create_branch (with conventional prefix), "
        "commit (selective staging, blocks master/main), "
        "status. Never uses 'git add .'."
    )

    def _run(
        self,
        command: str,
        branch_name: str = None,
        message: str = None,
    ) -> str:
        if command == "create_branch":
            result = _git_create_branch(branch_name)
        elif command == "commit":
            result = _git_commit(message)
        elif command == "status":
            result = _git_status()
        else:
            result = (
                f"Invalid command: '{command}'. "
                f"Valid commands: create_branch, commit, status."
            )

        audit_log(
            "git_operations",
            {"command": command, "branch_name": branch_name, "message": message},
            result[:200],
            status=(
                "OK" if "BLOCKED" not in result and "Error" not in result else "ERROR"
            ),
        )
        return result
