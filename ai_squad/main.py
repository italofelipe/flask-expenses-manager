"""
Auraxis AI Squad — Backend Only Mode (5-task pipeline).

Pipeline:
  PM (plan) → Dev (read) → Dev (write) → Dev (review) → QA (test)

The 5-task architecture addresses these root causes of previous failures:
  - Task 2 (READ): prevents blind overwrites by reading files first.
  - Task 4 (REVIEW): catches migration/model inconsistencies before commit.
  - Migration Decision Rules: teaches agents when to rename vs add columns.
  - Alembic history tool: reveals what columns already exist in the database.
  - Validation tool: machine-checks model vs migration consistency.
  - Timeout fix: uses DEFAULT_TIMEOUT (120s) for git commit (pre-commit hooks).

HOW TO USE:
  Edit BRIEFING at the bottom of this file, then run:
    cd ai_squad && python main.py

BRIEFING TIPS:
  - Reference the TASKS.md ID explicitly (e.g., "B8").
  - Name the exact files to touch — the agent reads them before writing.
  - Describe what to ADD, not what the full file should look like.
  - For renames: say RENAME explicitly, not ADD.

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
    ReadAlembicHistoryTool,
    ReadContextFileTool,
    ReadGovernanceFileTool,
    ReadPendingTasksTool,
    ReadProjectFileTool,
    ReadSchemaTool,
    ReadTasksSectionTool,
    RunTestsTool,
    ValidateMigrationConsistencyTool,
    WriteFileTool,
)

load_dotenv()

# =========================================================================
# MIGRATION DECISION RULES — injected into agent backstory/task descriptions
# so LLMs know when to use each Alembic operation.
# =========================================================================
MIGRATION_RULES = (
    "MIGRATION DECISION RULES (memorize these):\n"
    "- NEW column that never existed: op.add_column()\n"
    "- RENAME existing column: op.alter_column(new_column_name=) "
    "or raw op.execute('ALTER TABLE x RENAME COLUMN old TO new'). "
    "NEVER use add_column for a rename — it creates a duplicate.\n"
    "- CHANGE type/nullable of existing column: op.alter_column()\n"
    "- REMOVE column: op.drop_column()\n"
    "- To know which columns ALREADY EXIST: call read_alembic_history(table).\n"
    "- If the briefing says 'rename X to Y', the migration MUST use "
    "ALTER COLUMN RENAME, not add_column + drop_column."
)


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
        self.rah = ReadAlembicHistoryTool()
        self.rs = ReadSchemaTool()

        # Validation tools
        self.vmc = ValidateMigrationConsistencyTool()

        # Execution tools
        self.rtst = RunTestsTool()

        # Write + Git tools
        self.wf = WriteFileTool()
        self.git = GitOpsTool()

    def run_backend_workflow(self, briefing: str):
        """
        5-task pipeline: Plan -> Read -> Write -> Review -> Test.

        Task 2 (Read) prevents blind overwrites.
        Task 4 (Review) catches model/migration inconsistencies
        BEFORE committing, so agents self-correct.
        """

        # --- AGENTS ---
        manager = Agent(
            role="Gerente de Projeto Auraxis",
            goal=(
                "Produce a CONCRETE implementation plan with exact "
                "file paths, exact code changes, correct migration "
                "operations, and correct migration chain. "
                "Never produce a plan that results in zero code changes."
            ),
            backstory=(
                "Technical lead who reads before planning. "
                "You use read_pending_tasks to see what needs doing, "
                "read_tasks_section to zoom into a task, "
                "read_governance_file for product direction, and "
                "read_alembic_history to check existing DB columns.\n\n"
                + MIGRATION_RULES
            ),
            tools=[self.rpt, self.rts, self.rcf, self.rgf, self.rah],
            verbose=True,
            allow_delegation=True,
        )

        backend_dev = Agent(
            role="Senior Backend Engineer",
            goal=(
                "Read every existing file before modifying it. "
                "Add new fields/methods to existing code, never replace. "
                "Write complete, working Python following project patterns. "
                "After writing, ALWAYS validate migration consistency."
            ),
            backstory=(
                "Expert in Python, Flask, SQLAlchemy (db.Model style), "
                "Marshmallow, and Graphene (NOT Ariadne). "
                "Your rule: read_project_file BEFORE write_file_content. "
                "You integrate new code into what already exists.\n\n" + MIGRATION_RULES
            ),
            tools=[
                self.rpf,
                self.lpf,
                self.glm,
                self.rah,
                self.rs,
                self.rcf,
                self.vmc,
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
            backstory=(
                "Rigorous tester who runs the full suite and " "reports honestly."
            ),
            tools=[self.rtst, self.rcf],
            verbose=True,
        )

        # --- TASK 1: PLAN ---
        task_plan = Task(
            description=(
                "BOOTSTRAP (execute in order):\n"
                "1. read_pending_tasks() — focused pending work\n"
                "2. read_tasks_section('<task_id>') — zoom into task\n"
                "3. read_context_file('04_architecture_snapshot.md')\n"
                "4. read_governance_file('product.md')\n"
                "5. read_alembic_history('<table>') — see existing "
                "columns in DB\n\n"
                f'USER BRIEFING: "{briefing}"\n\n'
                "Produce a CONCRETE plan. Include:\n"
                "- Task ID being implemented\n"
                "- Exact file paths to modify or create\n"
                "- For each file: what to ADD (not replace)\n"
                "- Migration needed? If yes: for EACH column state "
                "the operation: ADD (new), RENAME (existing->new), "
                "ALTER (change type), DROP\n"
                "- Implementation order (dependencies first)\n\n"
                + MIGRATION_RULES
                + "\n\n"
                "CRITICAL: If briefing names a task ID, that task "
                "MUST be implemented. 'Nothing to do' is never valid."
            ),
            expected_output=(
                "Numbered list:\n"
                "1. Task ID: <id>\n"
                "2. Files to MODIFY: <path> — <what to add>\n"
                "3. Files to CREATE: <path> — <purpose>\n"
                "4. Migration ops: <column>: <ADD|RENAME|ALTER|DROP>\n"
                "5. Order: <step by step>"
            ),
            agent=manager,
        )

        # --- TASK 2: READ (guard against blind overwrites) ---
        task_read = Task(
            description=(
                "READ PHASE — execute before writing anything.\n\n"
                "For every file listed in the plan:\n"
                "1. list_project_files('<dir>') to confirm what exists\n"
                "2. read_project_file('<path>') for FULL current content\n"
                "3. read_schema() to read schema.graphql\n"
                "4. get_latest_migration() for correct down_revision\n"
                "5. read_alembic_history('<table>') for existing columns\n\n"
                "Output a READING REPORT listing:\n"
                "- Each file read: classes, fields, methods found\n"
                "- The latest migration revision ID\n"
                "- Columns that ALREADY EXIST in the database\n"
                "- Conflicts/risks between plan and reality\n"
                "- For each planned migration op, confirm: is this truly "
                "a new column, or does a column with similar name already "
                "exist (suggesting RENAME instead of ADD)?\n\n"
                "DO NOT write any code yet. This task is read-only."
            ),
            expected_output=(
                "Reading report:\n"
                "- File: <path> | Contents: <classes/fields/methods>\n"
                "- Latest migration revision: <id>\n"
                "- Existing DB columns for target table: <list>\n"
                "- Migration op validation: <column>: <confirmed|conflict>\n"
                "- Conflicts/risks: <any issues spotted>"
            ),
            agent=backend_dev,
            context=[task_plan],
        )

        # --- TASK 3: WRITE ---
        task_code = Task(
            description=(
                "WRITE PHASE — implement based on plan + reading report.\n\n"
                "RULES (non-negotiable):\n"
                "1. Use the reading report as your base\n"
                "2. For existing files: take the FULL content you read, "
                "add new fields/methods, write the complete file\n"
                "3. For new files: follow project patterns\n"
                "4. Use db.Model style (NOT declarative Base)\n"
                "5. Use Graphene (NOT Ariadne) for GraphQL\n"
                "6. Set down_revision to revision from reading report\n"
                "7. " + MIGRATION_RULES + "\n"
                "8. After writing ALL files: "
                "git_operations(command='status') to verify\n"
                "9. DO NOT create branch or commit yet — the REVIEW "
                "phase will validate first.\n\n"
                "NEVER claim a file was written without calling "
                "write_file_content."
            ),
            expected_output=(
                "List of all files written:\n"
                "- <path>: <one-line summary of changes>\n"
                "Git status output showing modified files."
            ),
            agent=backend_dev,
            context=[task_plan, task_read],
        )

        # --- TASK 4: REVIEW (self-check before commit) ---
        task_review = Task(
            description=(
                "REVIEW PHASE — validate consistency before committing.\n\n"
                "Execute these checks IN ORDER:\n"
                "1. validate_migration_consistency(\n"
                "     model_path='<model file>',\n"
                "     migration_path='<migration file>'\n"
                "   )\n"
                "2. read_project_file('<model file>') — verify all "
                "original fields are still present\n"
                "3. read_project_file('<schema file>') — verify all "
                "original schemas are still present\n"
                "4. read_project_file('<migration file>') — verify "
                "down_revision is correct\n\n"
                "DECISION:\n"
                "- If validate_migration_consistency returns ISSUES: "
                "FIX the files using write_file_content, then re-validate.\n"
                "- If all checks pass: proceed to create branch and commit.\n"
                "  git_operations(command='create_branch', "
                "branch_name='feat/<task-id>-<description>')\n"
                "  git_operations(command='commit', "
                "message='feat(<scope>): <description>')\n\n"
                "This task is the GATEKEEPER. Do not commit if any "
                "check shows ISSUES."
            ),
            expected_output=(
                "Review results:\n"
                "- Migration consistency: CONSISTENT or ISSUES (+ fixes)\n"
                "- Model fields preserved: YES or NO (+ what was lost)\n"
                "- Schema preserved: YES or NO (+ what was lost)\n"
                "- down_revision correct: YES or NO\n"
                "- Branch created: <name>\n"
                "- Commit: <hash or 'blocked — issues found'>"
            ),
            agent=backend_dev,
            context=[task_plan, task_read, task_code],
        )

        # --- TASK 5: TEST ---
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
            context=[task_review],
        )

        # --- CREW ---
        crew = Crew(
            agents=[manager, backend_dev, qa_engineer],
            tasks=[task_plan, task_read, task_code, task_review, task_test],
            process=Process.sequential,
            verbose=True,
        )

        return crew.kickoff()


# =================================================================
# BRIEFING — Edit this to tell the squad what to implement.
#
# Be specific:
#   - Task ID from TASKS.md (e.g., "B8")
#   - Exact fields/behavior expected
#   - Files to touch (the agent will read them before writing)
#   - For column renames: say RENAME explicitly
# =================================================================

if __name__ == "__main__":
    print("### Auraxis AI Squad — BACKEND ONLY (5-task pipeline) ###")
    print(f"Project root: {os.path.abspath('.')}")
    print()

    BRIEFING = (
        "Implement task B8: User Profile V1 minimum fields.\n"
        "Files to modify:\n"
        "  - app/models/user.py: ADD columns to existing User model "
        "(keep ALL existing fields and relationships):\n"
        "    * state_uf (db.String(2), nullable=True)\n"
        "    * occupation (db.String(128), nullable=True)\n"
        "    * investor_profile (db.String(32), nullable=True, "
        "values: conservador/explorador/entusiasta)\n"
        "    * financial_objectives (db.Text, nullable=True)\n"
        "    * RENAME monthly_income TO monthly_income_net "
        "(db.Numeric(10,2), nullable=True)\n"
        "    * ADD hybrid_property monthly_income that reads/writes "
        "monthly_income_net for backward compatibility\n"
        "  - app/schemas/user_schemas.py: ADD the new fields to "
        "UserProfileSchema and UserCompleteSchema.\n"
        "  - migrations/versions/: CREATE Alembic migration:\n"
        "    * RENAME column monthly_income to monthly_income_net "
        "(use op.alter_column or ALTER TABLE RENAME COLUMN)\n"
        "    * ADD columns: state_uf, occupation, investor_profile, "
        "financial_objectives\n"
        "    * down_revision = latest (use get_latest_migration)\n"
        "Do NOT create new files for schema or service."
    )

    squad = AuraxisSquad()
    squad.run_backend_workflow(BRIEFING)
