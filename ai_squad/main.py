"""
Auraxis AI Squad — Backend Only Mode.

Runs a 4-task pipeline using CrewAI:
  PM (plan) → Backend Dev (read) → Backend Dev (write) → QA (test)

The extra "read" task is the fix for the root cause of the previous failure:
agents were writing files without reading what already existed, causing
overwrites and loss of existing code.

HOW TO USE:
  Edit BRIEFING at the bottom of this file, then run:
    cd ai_squad && python main.py

BRIEFING TIPS:
  - Reference the TASKS.md ID explicitly (e.g., "B8").
  - Name the exact files to touch — the agent reads them before writing.
  - Describe what to ADD, not what the full file should look like.

References:
- .context/07_operational_cycle.md — full delivery cycle
- .context/04_architecture_snapshot.md — codebase structure
- ai_squad/AGENT_ARCHITECTURE.md — agent registry and tools
"""

import os

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv
from tools.project_tools import (
    GetLatestMigrationTool,
    GitOpsTool,
    ListProjectFilesTool,
    ReadContextFileTool,
    ReadGovernanceFileTool,
    ReadPendingTasksTool,
    ReadProjectFileTool,
    ReadSchemaTool,
    ReadTasksSectionTool,
    RunTestsTool,
    WriteFileTool,
)

load_dotenv()


class AuraxisSquad:
    def __init__(self):
        # Discovery tools (read-only, no security risk)
        self.rpt = ReadPendingTasksTool()
        self.rts = ReadTasksSectionTool()
        self.rcf = ReadContextFileTool()
        self.rgf = ReadGovernanceFileTool()
        self.rpf = ReadProjectFileTool()
        self.lpf = ListProjectFilesTool()
        self.glm = GetLatestMigrationTool()
        self.rs = ReadSchemaTool()

        # Execution tools
        self.rtst = RunTestsTool()

        # Write + Git tools
        self.wf = WriteFileTool()
        self.git = GitOpsTool()

    def run_backend_workflow(self, briefing: str):
        """
        4-task pipeline: Plan → Read → Write → Test.
        The Read task is the guard that prevents the Write task from
        overwriting existing files with hallucinated content.
        """

        # --- AGENTS ---
        manager = Agent(
            role="Gerente de Projeto Auraxis",
            goal=(
                "Produce a CONCRETE implementation plan with exact file paths, "
                "exact code changes, and correct migration chain. "
                "Never produce a plan that results in zero code changes."
            ),
            backstory=(
                "Technical lead who reads before planning. "
                "You use read_pending_tasks to see what needs to be done, "
                "read_tasks_section to zoom into a task, and "
                "read_governance_file to check product direction."
            ),
            tools=[self.rpt, self.rts, self.rcf, self.rgf],
            verbose=True,
            allow_delegation=True,
        )

        backend_dev = Agent(
            role="Senior Backend Engineer",
            goal=(
                "Read every existing file before modifying it. "
                "Add new fields/methods to existing code — never replace it. "
                "Write complete, working Python that follows the project patterns."
            ),
            backstory=(
                "Expert in Python, Flask, SQLAlchemy (db.Model style), "
                "Marshmallow, and Graphene (NOT Ariadne). "
                "Your rule: read_project_file BEFORE write_file_content. "
                "You integrate new code into what already exists."
            ),
            tools=[
                self.rpf,
                self.lpf,
                self.glm,
                self.rs,
                self.rcf,
                self.wf,
                self.git,
            ],
            verbose=True,
        )

        qa_engineer = Agent(
            role="QA Engineer",
            goal=(
                "Run pytest, report exact pass/fail counts and coverage. "
                "Flag FAIL if coverage < 85% or any test fails."
            ),
            backstory=("Rigorous tester who runs the full suite and reports honestly."),
            tools=[self.rtst, self.rcf],
            verbose=True,
        )

        # --- TASK 1: PLAN ---
        task_plan = Task(
            description=(
                "BOOTSTRAP (execute in order):\n"
                "1. read_pending_tasks() — focused list of pending work\n"
                "2. read_tasks_section('<task_id>') — zoom into the task\n"
                "3. read_context_file('04_architecture_snapshot.md')\n"
                "4. read_governance_file('product.md')\n\n"
                f'USER BRIEFING: "{briefing}"\n\n'
                "Produce a CONCRETE plan. Include:\n"
                "- Task ID being implemented\n"
                "- Exact file paths to modify (existing) or create (new)\n"
                "- For each file: what to ADD (not replace)\n"
                "- Migration needed? Yes/No. If yes: what columns to add\n"
                "- Implementation order (dependencies first)\n\n"
                "CRITICAL: If briefing names a task ID, that task MUST be "
                "implemented. 'Nothing to do' is never acceptable."
            ),
            expected_output=(
                "Numbered list:\n"
                "1. Task ID: <id>\n"
                "2. Files to MODIFY: <path> — <what to add>\n"
                "3. Files to CREATE: <path> — <purpose>\n"
                "4. Migration: <yes/no> — <columns if yes>\n"
                "5. Order: <step by step>"
            ),
            agent=manager,
        )

        # --- TASK 2: READ (guard against blind overwrites) ---
        task_read = Task(
            description=(
                "READ PHASE — execute before writing anything.\n\n"
                "For every file listed in the plan:\n"
                "1. list_project_files('<directory>') to confirm what exists\n"
                "2. read_project_file('<path>') to read the FULL current content\n"
                "3. read_schema() to read schema.graphql\n"
                "4. get_latest_migration() to get the correct down_revision\n\n"
                "Output a READING REPORT listing:\n"
                "- Each file read and its key contents (classes, fields, methods)\n"
                "- The latest migration revision ID\n"
                "- Any conflicts or risks spotted between plan and reality\n\n"
                "DO NOT write any code yet. This task is read-only."
            ),
            expected_output=(
                "Reading report:\n"
                "- File: <path> | Key contents: <classes/fields/methods found>\n"
                "- Latest migration revision: <id>\n"
                "- Conflicts/risks: <any issues spotted>"
            ),
            agent=backend_dev,
            context=[task_plan],
        )

        # --- TASK 3: WRITE ---
        task_code = Task(
            description=(
                "WRITE PHASE — implement based on the plan and reading report.\n\n"
                "RULES (non-negotiable):\n"
                "1. Use the reading report from the previous task as your base\n"
                "2. For existing files: take the FULL content you read, add the "
                "new fields/methods, write the complete updated file\n"
                "3. For new files: create from scratch following project patterns\n"
                "4. Use db.Model style (NOT declarative Base) for SQLAlchemy\n"
                "5. Use Graphene (NOT Ariadne) for GraphQL\n"
                "6. Set migration down_revision to revision ID from reading report\n"
                "7. After writing: git_operations(command='status') to verify\n"
                "8. After verifying: git_operations(command='create_branch', "
                "branch_name='feat/<task-id>-<short-description>')\n"
                "9. Then: git_operations(command='commit', "
                "message='feat(<scope>): <description>')\n\n"
                "NEVER claim a file was written without calling write_file_content."
            ),
            expected_output=(
                "List of all files written:\n"
                "- <path>: <one-line summary of changes>\n"
                "Git branch created: <branch name>\n"
                "Commit hash: <hash from git status>"
            ),
            agent=backend_dev,
            context=[task_plan, task_read],
        )

        # --- TASK 4: TEST ---
        task_test = Task(
            description=(
                "TEST PHASE — validate the implementation.\n\n"
                "1. run_backend_tests()\n"
                "2. Report exact numbers: X passed, Y failed\n"
                "3. Report coverage percentage\n"
                "4. Status: PASS (coverage >= 85%, 0 failures) or FAIL\n"
                "5. If FAIL: quote the exact error messages\n\n"
                "Consult read_context_file('05_quality_and_gates.md') "
                "for the Definition of Done checklist."
            ),
            expected_output=(
                "Test results:\n"
                "- Passed: X | Failed: Y\n"
                "- Coverage: XX%\n"
                "- Status: PASS or FAIL\n"
                "- Errors (if any): <exact messages>"
            ),
            agent=qa_engineer,
            context=[task_code],
        )

        # --- CREW ---
        crew = Crew(
            agents=[manager, backend_dev, qa_engineer],
            tasks=[task_plan, task_read, task_code, task_test],
            process=Process.sequential,
            verbose=True,
        )

        return crew.kickoff()


# =============================================================================
# BRIEFING — Edit this to tell the squad what to implement.
#
# Be specific:
#   - Task ID from TASKS.md (e.g., "B8")
#   - Exact fields/behavior expected
#   - Files to touch (the agent will read them before writing)
# =============================================================================

if __name__ == "__main__":
    print("### Auraxis AI Squad — BACKEND ONLY (4-task pipeline) ###")
    print(f"Project root: {os.path.abspath('.')}")
    print()

    BRIEFING = (
        "Implement task B8: User Profile V1 minimum fields. "
        "Files to modify:\n"
        "  - app/models/user.py: ADD these columns to the existing User model "
        "(keep all existing fields): "
        "state_uf (db.String(2), nullable=True), "
        "occupation (db.String(128), nullable=True), "
        "investor_profile (db.String(32), nullable=True, "
        "values: conservador/explorador/entusiasta), "
        "financial_objectives (db.Text, nullable=True), "
        "monthly_income_net (db.Numeric(10,2), nullable=True). "
        "ADD a hybrid_property monthly_income that reads/writes "
        "monthly_income_net for backward compatibility.\n"
        "  - app/schemas/user_schemas.py: ADD the 5 new fields to "
        "UserProfileSchema and UserCompleteSchema. "
        "ADD monthly_income_net as alias in UserCompleteSchema.\n"
        "  - migrations/versions/: CREATE a new Alembic migration that "
        "adds the 5 columns to the 'users' table. "
        "down_revision must be the latest migration revision (use "
        "get_latest_migration to find it).\n"
        "Do NOT create new files for schema or service — modify existing ones."
    )

    squad = AuraxisSquad()
    squad.run_backend_workflow(BRIEFING)
