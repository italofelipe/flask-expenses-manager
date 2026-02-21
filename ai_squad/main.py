"""
Auraxis AI Squad — Backend Only Mode.

Runs a 3-agent pipeline (PM → Backend Dev → QA) using CrewAI.
Frontend and DevOps agents are disabled until the project has a frontend.

The PM agent executes the .context/ bootstrap sequence before planning,
as defined in .context/README.md and .context/03_agentic_workflow.md.

References:
- ai_squad/AGENT_ARCHITECTURE.md — agent registry and tools
- .context/03_agentic_workflow.md — agentic operational loop
- .context/05_quality_and_gates.md — quality gates and Definition of Done
"""

import os

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv
from tools.project_tools import (
    GitOpsTool,
    ReadContextFileTool,
    ReadGovernanceFileTool,
    ReadSchemaTool,
    ReadTasksTool,
    RunTestsTool,
    WriteFileTool,
)

load_dotenv()


class AuraxisSquad:
    def __init__(self):
        # Read-only tools
        self.rt = ReadTasksTool()
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
                "alignment with product.md, and compliance with steering.md."
            ),
            backstory=(
                "Technical lead focused on Clean Architecture and TASKS.md. "
                "You always start by reading the .context/ knowledge base "
                "to understand the project's current state before planning."
            ),
            tools=[self.rt, self.rcf, self.rgf],
            verbose=True,
            allow_delegation=True,
        )

        backend_dev = Agent(
            role="Senior Backend Engineer",
            goal=(
                "Implement business logic, models, services, and "
                "GraphQL resolvers following CODING_STANDARDS.md."
            ),
            backstory=(
                "Expert in Python, Flask, SQLAlchemy, and Ariadne GraphQL. "
                "You consult .context/04_architecture_snapshot.md for the "
                "codebase structure before writing any code."
            ),
            tools=[self.rt, self.rs, self.rcf, self.wf, self.git],
            verbose=True,
        )

        qa_engineer = Agent(
            role="QA Engineer",
            goal=(
                "Validate backend changes against quality gates "
                "defined in .context/05_quality_and_gates.md."
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
                "1. read_context_file('README.md')\n"
                "2. read_context_file('01_sources_of_truth.md')\n"
                "3. read_context_file('04_architecture_snapshot.md')\n"
                "4. read_governance_file('steering.md')\n"
                "5. read_governance_file('product.md')\n"
                "6. read_tasks()\n\n"
                f'USER BRIEFING: "{briefing}"\n\n'
                "Based on the bootstrap context and the user's briefing, "
                "define the next backend increment: which files to change, "
                "what models/services/resolvers to create or modify, "
                "and in what order."
            ),
            expected_output=(
                "A detailed technical plan listing which backend files "
                "will be created or modified, with rationale tied to "
                "TASKS.md priorities and product.md direction."
            ),
            agent=manager,
        )

        task_code = Task(
            description=(
                "Implement the backend changes as defined in the plan. "
                "Use migrations (Alembic) if the database schema changes. "
                "Follow the coding standards in CODING_STANDARDS.md. "
                "Every new Model must have a corresponding Marshmallow Schema."
            ),
            expected_output=(
                "Python code implemented and saved to the correct files. "
                "List of all files created or modified."
            ),
            agent=backend_dev,
            context=[task_plan],
        )

        task_test = Task(
            description=(
                "Run the test suite (pytest) to validate backend changes. "
                "Check that coverage meets the 85% minimum threshold. "
                "Consult .context/05_quality_and_gates.md for the full "
                "Definition of Done checklist."
            ),
            expected_output=(
                "Test results: pass/fail summary, coverage percentage, "
                "and any error logs that need fixing."
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


if __name__ == "__main__":
    print("### Auraxis AI Squad - Mode: BACKEND ONLY ###")
    print(f"Project root: {os.path.abspath('.')}")
    print()

    briefing_usuario = (
        "Analise o status atual no TASKS.md e identifique "
        "se há algo pendente nos modelos de Investimento."
    )

    squad = AuraxisSquad()
    squad.run_backend_workflow(briefing_usuario)
