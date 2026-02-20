"""
Auraxis AI Squad — Project Tools (Security-Hardened).

This module provides all tools available to CrewAI agents for interacting
with the Auraxis codebase. Every tool enforces security boundaries defined
in tool_security.py before performing any operation.

Architecture:
- Read tools: read_tasks, read_schema, read_context_file, read_governance_file
- Write tools: write_file_content (path-validated)
- Execution tools: run_backend_tests (timeout-enforced)
- Infrastructure tools: check_aws_status (timeout-enforced)
- Git tools: git_operations (selective staging, branch prefix validation)

Security Guarantees:
- No file write outside WRITABLE_DIRS (app/, tests/, migrations/, scripts/, docs/).
- No write to PROTECTED_FILES (.env, run.py, Dockerfiles, etc.).
- No git staging of sensitive patterns (.env, *.pem, *.key, etc.).
- All subprocess calls have enforced timeouts.
- Every tool invocation is audit-logged to ai_squad/logs/tool_audit.log.

Integration with .context/:
- read_context_file() gives agents access to the SDD/agentic knowledge base.
- read_governance_file() gives agents access to product.md and steering.md.
- This bridges the gap between ai_squad/ (execution) and .context/ (governance).

References:
- ai_squad/tools/tool_security.py — security primitives used here
- .context/03_agentic_workflow.md — agent operational loop
- .context/05_quality_and_gates.md — quality gates enforced by run_backend_tests
- steering.md — branching conventions enforced by git_operations
"""

import fnmatch
import os

from langchain.tools import tool
from tools.tool_security import (
    CONVENTIONAL_BRANCH_PREFIXES,
    GIT_STAGE_BLOCKLIST,
    PROJECT_ROOT,
    audit_log,
    safe_subprocess,
    validate_write_path,
)


class ProjectTools:
    """
    Centralized tool registry for Auraxis CrewAI agents.

    All methods are static and decorated with @tool() for LangChain/CrewAI
    compatibility. Each tool enforces security boundaries via tool_security.py.

    Usage in main.py:
        tools = ProjectTools()
        agent = Agent(tools=[tools.read_tasks, tools.write_file_content, ...])
    """

    # -------------------------------------------------------------------
    # READ TOOLS — safe, read-only access to project files
    # -------------------------------------------------------------------

    @tool("read_tasks")
    def read_tasks() -> str:
        """
        Read TASKS.md to understand the current project status, backlog,
        priorities, and risk register.

        Returns:
            Full content of TASKS.md, or error message if file not found.

        Note:
            TASKS.md is the primary source of truth for task status
            (see .context/01_sources_of_truth.md).
        """
        try:
            with open(PROJECT_ROOT / "TASKS.md", "r") as f:
                content = f.read()
            audit_log("read_tasks", {}, f"read {len(content)} chars")
            return content
        except FileNotFoundError:
            audit_log("read_tasks", {}, "TASKS.md not found", status="ERROR")
            return "ERROR: TASKS.md not found at project root."

    @tool("read_schema")
    def read_schema() -> str:
        """
        Read schema.graphql to understand GraphQL API contracts
        (types, queries, mutations, inputs).

        Returns:
            Full content of schema.graphql, or error message if not found.

        Note:
            The schema defines the public API contract. Any changes must
            preserve backward compatibility unless explicitly approved.
        """
        try:
            with open(PROJECT_ROOT / "schema.graphql", "r") as f:
                content = f.read()
            audit_log("read_schema", {}, f"read {len(content)} chars")
            return content
        except FileNotFoundError:
            audit_log("read_schema", {}, "schema.graphql not found", status="ERROR")
            return "ERROR: schema.graphql not found at project root."

    @tool("read_context_file")
    def read_context_file(filename: str) -> str:
        """
        Read a file from the .context/ knowledge base directory.

        This tool gives agents access to the SDD workflow, agentic workflow,
        architecture snapshot, quality gates, and templates.

        Args:
            filename: Relative path within .context/. Examples:
                - "README.md" (bootstrap and reading order)
                - "01_sources_of_truth.md" (document authority hierarchy)
                - "02_sdd_workflow.md" (Spec-Driven Development phases)
                - "03_agentic_workflow.md" (agent operational loop)
                - "04_architecture_snapshot.md" (codebase structure)
                - "05_quality_and_gates.md" (quality gates and DoD)
                - "06_context_backlog.md" (knowledge base improvements)
                - "templates/feature_spec_template.md"
                - "templates/handoff_template.md"

        Returns:
            File content, or error message if not found or path escapes.

        Security:
            Path is resolved and validated to stay within .context/.
            Any '../' traversal attempt is blocked.
        """
        context_dir = PROJECT_ROOT / ".context"
        target = (context_dir / filename).resolve()

        # Security: prevent path escape outside .context/
        if not str(target).startswith(str(context_dir.resolve())):
            audit_log(
                "read_context_file",
                {"filename": filename},
                "PATH ESCAPE BLOCKED",
                status="BLOCKED",
            )
            return "BLOCKED: path escapes .context/ directory."

        try:
            with open(target, "r") as f:
                content = f.read()
            audit_log(
                "read_context_file",
                {"filename": filename},
                f"read {len(content)} chars",
            )
            return content
        except FileNotFoundError:
            audit_log(
                "read_context_file",
                {"filename": filename},
                "file not found",
                status="ERROR",
            )
            return f"ERROR: .context/{filename} not found."

    @tool("read_governance_file")
    def read_governance_file(filename: str) -> str:
        """
        Read a project governance file (product.md or steering.md).

        These files define product direction and execution governance.
        Agents should read these during the bootstrap phase before
        planning any work (see .context/03_agentic_workflow.md).

        Args:
            filename: Must be exactly "product.md" or "steering.md".

        Returns:
            File content, or error message if filename not allowed or not found.

        Security:
            Only product.md and steering.md are readable via this tool.
            This is a strict allowlist to prevent agents from reading
            arbitrary files at the project root.
        """
        allowed = {"product.md", "steering.md"}
        if filename not in allowed:
            audit_log(
                "read_governance_file",
                {"filename": filename},
                f"not in allowlist {allowed}",
                status="BLOCKED",
            )
            return f"BLOCKED: only {allowed} are readable via this tool."

        try:
            with open(PROJECT_ROOT / filename, "r") as f:
                content = f.read()
            audit_log(
                "read_governance_file",
                {"filename": filename},
                f"read {len(content)} chars",
            )
            return content
        except FileNotFoundError:
            audit_log(
                "read_governance_file",
                {"filename": filename},
                "file not found",
                status="ERROR",
            )
            return f"ERROR: {filename} not found at project root."

    # -------------------------------------------------------------------
    # WRITE TOOLS — path-validated file operations
    # -------------------------------------------------------------------

    @tool("write_file_content")
    def write_file_content(path: str, content: str) -> str:
        """
        Write content to a file. The path must be inside an allowed directory.

        Allowed directories: app/, tests/, migrations/, scripts/, docs/, ai_squad/logs/.
        Protected files (.env, run.py, Dockerfiles, etc.) are always blocked.

        Args:
            path: Relative path from project root (e.g., "app/models/goal.py").
            content: Full file content to write.

        Returns:
            Success message, or "BLOCKED: ..." if path validation fails.

        Security:
            Uses validate_write_path() which enforces:
            - Allowlist of writable directories
            - Denylist of protected files
            - Blocked file extensions (.env, .pem, .key, .secret)
            - Path traversal prevention (../ and symlinks)
        """
        try:
            resolved = validate_write_path(path)
        except PermissionError as e:
            audit_log(
                "write_file_content",
                {"path": path, "content_len": len(content)},
                str(e),
                status="BLOCKED",
            )
            return f"BLOCKED: {e}"

        # Ensure parent directories exist
        resolved.parent.mkdir(parents=True, exist_ok=True)

        with open(resolved, "w") as f:
            f.write(content)

        audit_log(
            "write_file_content",
            {
                "path": str(resolved.relative_to(PROJECT_ROOT)),
                "content_len": len(content),
            },
            "written successfully",
        )
        return f"File {path} written successfully."

    # -------------------------------------------------------------------
    # EXECUTION TOOLS — subprocess calls with timeout enforcement
    # -------------------------------------------------------------------

    @tool("run_backend_tests")
    def run_backend_tests() -> str:
        """
        Execute the pytest backend test suite and return the result.

        Runs with:
        - --tb=short: Concise traceback for failed tests.
        - -q: Quiet mode to reduce output noise.
        - -m "not schemathesis": Excludes property-based tests.
        - Timeout: 300 seconds (5 minutes max).

        Returns:
            Combined STDOUT and STDERR from pytest.

        Note:
            Quality gate: tests must pass before any commit.
            See .context/05_quality_and_gates.md for full gate list.
        """
        result = safe_subprocess(
            ["pytest", "-m", "not schemathesis", "--tb=short", "-q"],
            timeout=300,
        )
        output = f"STDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
        audit_log(
            "run_backend_tests",
            {},
            f"returncode={result['returncode']}",
        )
        return output

    @tool("check_aws_status")
    def check_aws_status() -> str:
        """
        Check basic AWS infrastructure status (EC2 instances).

        Requires AWS CLI configured with appropriate credentials.
        Timeout: 30 seconds.

        Returns:
            List of EC2 instances with InstanceId, State, and PublicIP.

        Note:
            This is a read-only operation. Actual deploy actions
            require human_input=True approval in the CrewAI task.
        """
        result = safe_subprocess(
            [
                "aws",
                "ec2",
                "describe-instances",
                "--query",
                "Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress]",
            ],
            timeout=30,
        )
        output = f"AWS Status:\n{result['stdout']}"
        if result["returncode"] != 0:
            output += f"\nError: {result['stderr']}"
        audit_log("check_aws_status", {}, output[:200])
        return output

    # -------------------------------------------------------------------
    # GIT TOOLS — safe git operations with selective staging
    # -------------------------------------------------------------------

    @tool("git_operations")
    def git_operations(
        command: str,
        branch_name: str = None,
        message: str = None,
    ) -> str:
        """
        Execute safe git operations with security guardrails.

        Supported commands:
        - 'create_branch': Create and switch to a new branch.
          Enforces conventional branch prefixes (feat/, fix/, refactor/, etc.).
        - 'commit': Stage and commit changes with SELECTIVE staging.
          Never uses 'git add .' — filters files against GIT_STAGE_BLOCKLIST.
        - 'status': Show current working tree status.

        Args:
            command: One of 'create_branch', 'commit', 'status'.
            branch_name: Required for 'create_branch'. Must start with a
                conventional prefix (feat/, fix/, refactor/, chore/, docs/,
                test/, perf/, security/).
            message: Required for 'commit'. The commit message.

        Returns:
            Operation result or "BLOCKED: ..." if validation fails.

        Security:
            - Branch names must follow conventional branching (steering.md).
            - Commit uses selective staging: lists changed files, filters out
              sensitive patterns (.env, *.pem, *.key, .coverage, etc.),
              and only stages safe files.
            - All operations have subprocess timeouts.
        """
        dispatch = {
            "create_branch": lambda: _git_create_branch(branch_name),
            "commit": lambda: _git_commit(message),
            "status": _git_status,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (
                "ERROR: invalid command. "
                "Supported: 'create_branch', 'commit', 'status'."
            )
        return handler()


# -------------------------------------------------------------------
# Git helper functions (extracted to reduce cyclomatic complexity)
# -------------------------------------------------------------------


def _git_create_branch(branch_name: str | None) -> str:
    """Create a new branch with conventional prefix validation."""
    if not branch_name:
        return "ERROR: branch_name is required for create_branch."

    if not branch_name.startswith(CONVENTIONAL_BRANCH_PREFIXES):
        audit_log(
            "git_operations",
            {"command": "create_branch", "branch_name": branch_name},
            "invalid branch prefix",
            status="BLOCKED",
        )
        return (
            f"BLOCKED: branch '{branch_name}' must start with "
            f"one of {CONVENTIONAL_BRANCH_PREFIXES}"
        )

    result = safe_subprocess(["git", "checkout", "-b", branch_name], timeout=15)
    audit_log(
        "git_operations",
        {"command": "create_branch", "branch_name": branch_name},
        result["stdout"],
    )
    if result["returncode"] != 0:
        return f"ERROR: {result['stderr']}"
    return f"Branch '{branch_name}' created and checked out."


def _git_collect_changed_files() -> set[str]:
    """Collect all changed, staged, and untracked files."""
    all_files: set[str] = set()
    for cmd in [
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]:
        result = safe_subprocess(cmd, timeout=10)
        for f in result["stdout"].strip().split("\n"):
            if f.strip():
                all_files.add(f.strip())
    return all_files


def _git_filter_safe_files(
    all_files: set[str],
) -> tuple[list[str], list[str]]:
    """Split files into safe and blocked lists based on GIT_STAGE_BLOCKLIST."""
    safe_files: list[str] = []
    blocked_files: list[str] = []
    for filepath in sorted(all_files):
        is_blocked = any(
            fnmatch.fnmatch(filepath, pattern)
            or fnmatch.fnmatch(os.path.basename(filepath), pattern)
            for pattern in GIT_STAGE_BLOCKLIST
        )
        if is_blocked:
            blocked_files.append(filepath)
        else:
            safe_files.append(filepath)
    return safe_files, blocked_files


def _git_commit(message: str | None) -> str:
    """Commit with selective staging (never 'git add .')."""
    if not message:
        return "ERROR: message is required for commit."

    all_files = _git_collect_changed_files()
    if not all_files:
        return "No changed files to commit."

    safe_files, blocked_files = _git_filter_safe_files(all_files)

    if blocked_files:
        audit_log(
            "git_operations",
            {"command": "commit", "blocked_files": blocked_files},
            f"filtered {len(blocked_files)} unsafe files",
            status="OK",
        )

    if not safe_files:
        return f"No safe files to commit. Blocked files: {blocked_files}"

    stage_result = safe_subprocess(["git", "add"] + safe_files, timeout=15)
    if stage_result["returncode"] != 0:
        return f"ERROR staging files: {stage_result['stderr']}"

    commit_result = safe_subprocess(["git", "commit", "-m", message], timeout=30)
    audit_log(
        "git_operations",
        {
            "command": "commit",
            "staged_files": safe_files,
            "blocked_files": blocked_files,
            "message": message,
        },
        commit_result["stdout"],
    )
    if commit_result["returncode"] != 0:
        return f"ERROR committing: {commit_result['stderr']}"

    return (
        f"Committed {len(safe_files)} file(s) with message: {message}\n"
        f"Staged: {safe_files}\n"
        f"Excluded (blocked): {blocked_files if blocked_files else 'none'}"
    )


def _git_status() -> str:
    """Show current git working tree status."""
    result = safe_subprocess(["git", "status"], timeout=10)
    audit_log(
        "git_operations",
        {"command": "status"},
        result["stdout"][:200],
    )
    return result["stdout"]
