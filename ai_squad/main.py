"""
Auraxis AI Squad — Backend Only Mode.

Runs a 3-agent pipeline (PM → Backend Dev → QA) using CrewAI.
Frontend and DevOps agents are disabled until the project has a frontend.

HOW TO USE:
  Edit BRIEFING at the bottom of this file, then run:
    cd ai_squad && python main.py

BRIEFING TIPS:
  - Be specific: name the TASKS.md ID (e.g., "B8"), the fields, the files.
  - The PM reads TASKS.md automatically via read_pending_tasks — no need
    to ask it to "find what's pending" generically.
  - The more precise the briefing, the less the PM hallucinates.

References:
- ai_squad/AGENT_ARCHITECTURE.md — agent registry and tools
- .context/03_agentic_workflow.md — agentic operational loop
- .context/05_quality_and_gates.md — quality gates and Definition of Done
- .context/07_operational_cycle.md — full delivery cycle
"""

import os

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv
from tools.project_tools import (
    GitOpsTool,
    ReadContextFileTool,
    ReadGovernanceFileTool,
    ReadPendingTasksTool,
    ReadSchemaTool,
    ReadTasksSectionTool,
    ReadTasksTool,
    RunTestsTool,
    WriteFileTool,
)

load_dotenv()


class AuraxisSquad:
    def __init__(self):
        # Read-only tools
        self.rt = ReadTasksTool()
        self.rpt = ReadPendingTasksTool()  # focused view — avoids lost-in-middle
        self.rts = ReadTasksSectionTool()  # section-level read for large TASKS.md
        self.rs = ReadSchemaTool()
        self.rcf = ReadContextFileTool()
        self.rgf = ReadGovernanceFileTool()

        # Execution tools
        self.rtst = RunTestsTool()

        # Write tools
        self.wf = WriteFileTool()

        # Git tools
        self.git = GitOpsTool()

    def run_backend_workflow(self, briefing: str):
        """
        Run backend-only workflow: PM → Backend Dev → QA.
        Frontend and Deploy are dormant.
        """

        # --- AGENTS ---
        manager = Agent(
            role="Gerente de Projeto Auraxis",
            goal=(
                "Coordinate backend development ensuring code quality, "
                "alignment with product.md, and compliance with steering.md. "
                "Always produce a concrete plan with specific file names — "
                "never produce a plan that results in zero code changes."
            ),
            backstory=(
                "Technical lead focused on Clean Architecture and TASKS.md. "
                "You use read_pending_tasks to see what needs to be done, "
                "and read_tasks_section to zoom into a specific task. "
                "You never mark something as done without a code plan."
            ),
            tools=[self.rpt, self.rts, self.rcf, self.rgf],
            verbose=True,
            allow_delegation=True,
        )

        backend_dev = Agent(
            role="Senior Backend Engineer",
            goal=(
                "Implement business logic, models, services, and "
                "GraphQL resolvers following CODING_STANDARDS.md. "
                "You MUST write real Python code and save it using write_file_content. "
                "Never finish a task without writing at least one file."
            ),
            backstory=(
                "Expert in Python, Flask, SQLAlchemy, and Ariadne GraphQL. "
                "You consult .context/04_architecture_snapshot.md for the "
                "codebase structure before writing any code. "
                "You follow existing patterns: Model → Schema → Service → "
                "Controller → GraphQL resolver."
            ),
            tools=[self.rts, self.rs, self.rcf, self.wf, self.git],
            verbose=True,
        )

        qa_engineer = Agent(
            role="QA Engineer",
            goal=(
                "Validate backend changes against quality gates "
                "defined in .context/05_quality_and_gates.md. "
                "Run pytest and report exact results with coverage percentage."
            ),
            backstory=(
                "Rigorous tester. You run pytest and validate that "
                "the API contract is maintained. You check the quality "
                "gates before approving any changes."
            ),
            tools=[self.rtst, self.rcf],
            verbose=True,
        )

        # --- TASKS (Backend Only) ---
        task_plan = Task(
            description=(
                "BOOTSTRAP SEQUENCE (execute in order before planning):\n"
                "1. read_pending_tasks() — focused list of what needs doing\n"
                "2. read_tasks_section('<task_id>') — zoom into the specific task\n"
                "3. read_context_file('04_architecture_snapshot.md') — codebase\n"
                "4. read_governance_file('product.md') — product direction\n\n"
                f'USER BRIEFING: "{briefing}"\n\n'
                "Based on the bootstrap context and the user's briefing, produce a "
                "CONCRETE technical plan. The plan MUST include:\n"
                "- Exact file paths to create or modify (e.g., app/models/user.py)\n"
                "- What changes to make in each file\n"
                "- Whether a database migration is needed\n"
                "- The order of implementation\n\n"
                "IMPORTANT: If the briefing points to a specific task ID (e.g., B8), "
                "that task MUST be implemented. Do not conclude 'nothing to do'."
            ),
            expected_output=(
                "A detailed technical plan with:\n"
                "1. Task ID being implemented\n"
                "2. List of files to create/modify with specific changes\n"
                "3. Migration plan (if schema changes)\n"
                "4. Implementation order"
            ),
            agent=manager,
        )

        task_code = Task(
            description=(
                "Implement the backend changes exactly as defined in the plan.\n\n"
                "MANDATORY STEPS:\n"
                "1. Read .context/04_architecture_snapshot.md to understand patterns\n"
                "2. Read schema.graphql to understand current GraphQL contracts\n"
                "3. For each file in the plan: write the complete implementation\n"
                "4. Use write_file_content for every file created or modified\n"
                "5. After writing: use git_operations(command='status') to verify\n\n"
                "RULES:\n"
                "- Follow existing patterns (Model → Schema → Service → Resolver)\n"
                "- Every new Model MUST have a corresponding Marshmallow Schema\n"
                "- Use Alembic for migrations (write the migration file)\n"
                "- Never claim a file was written without actually writing it"
            ),
            expected_output=(
                "List of ALL files created or modified, with a one-line summary "
                "of what changed in each. Minimum: at least one file written."
            ),
            agent=backend_dev,
            context=[task_plan],
        )

        task_test = Task(
            description=(
                "Run the full test suite to validate backend changes.\n\n"
                "STEPS:\n"
                "1. run_backend_tests() — run pytest\n"
                "2. Report exact results: number of tests passed/failed\n"
                "3. Report coverage percentage\n"
                "4. If coverage < 85%: flag as FAIL\n"
                "5. If any tests fail: report the exact error messages\n\n"
                "Consult read_context_file('05_quality_and_gates.md') for "
                "the full Definition of Done checklist."
            ),
            expected_output=(
                "Test results:\n"
                "- Pass/fail: X passed, Y failed\n"
                "- Coverage: XX%\n"
                "- Status: PASS or FAIL\n"
                "- Error logs (if any failures)"
            ),
            agent=qa_engineer,
            context=[task_code],
        )

        # --- ORCHESTRATION (Backend Only) ---
        crew = Crew(
            agents=[manager, backend_dev, qa_engineer],
            tasks=[task_plan, task_code, task_test],
            process=Process.sequential,
            verbose=True,
        )

        return crew.kickoff()


# =============================================================================
# BRIEFING — Edit this to tell the squad what to implement.
#
# Tips:
#   - Reference the TASKS.md ID explicitly (e.g., "B8")
#   - Be specific about fields, files, and expected behavior
#   - The more precise, the less the PM will guess
# =============================================================================

if __name__ == "__main__":
    print("### Auraxis AI Squad - Mode: BACKEND ONLY ###")
    print(f"Project root: {os.path.abspath('.')}")
    print()

    BRIEFING = (
        "Implement task B8: User Profile V1 minimum fields. "
        "Add the following fields to the User model: "
        "state_uf (String, optional), occupation (String, optional), "
        "investor_profile (String enum: conservador/explorador/entusiasta, optional), "
        "financial_objectives (Text, optional). "
        "Rename monthly_income to monthly_income_net keeping backward compatibility "
        "(old field should still work as an alias or be migrated carefully). "
        "Files to touch: app/models/user.py, app/schemas/user_schema.py, "
        "and the GraphQL user type/mutations. "
        "Create an Alembic migration for the schema changes. "
        "Follow the existing patterns in the codebase."
    )

    squad = AuraxisSquad()
    squad.run_backend_workflow(BRIEFING)
