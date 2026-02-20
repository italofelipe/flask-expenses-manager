# Auraxis Agentic Architecture Manifesto

## 1. Overview

The Auraxis agent system uses the **CrewAI** framework for multi-agent orchestration.
The goal is to automate the SDLC (Software Development Life Cycle) with minimal human
intervention while following **Spec-Driven Development** governance.

### Knowledge Base Integration

All agents share the `.context/` knowledge base as their operational foundation.
The PM agent executes the bootstrap sequence defined in `.context/README.md` before
any planning. Other agents consult specific `.context/` files relevant to their role.

**Authoritative references:**
- `.context/01_sources_of_truth.md` — document authority hierarchy
- `.context/03_agentic_workflow.md` — agent operational loop and handoff protocol
- `.context/05_quality_and_gates.md` — quality gates and Definition of Done
- `steering.md` — execution governance, branching, and commit conventions
- `product.md` — product vision and functional scope

## 2. Agent Registry (Roles)

| Agent | Responsibility | Technical Specialty | Key Tools |
| :--- | :--- | :--- | :--- |
| **Project Manager (PM)** | Orchestration and Prioritization | Product Vision, TASKS.md | read_tasks, read_context_file, read_governance_file |
| **Backend Dev** | Server Logic and DB | Flask, SQLAlchemy, GraphQL, Alembic | read_tasks, read_schema, read_context_file, write_file_content |
| **Frontend Dev** | Interface and UX | Next.js/Angular/Flutter | write_file_content |
| **QA Engineer** | Validation and Security | Pytest, Smoke Tests, OWASP | run_backend_tests, read_context_file |
| **DevOps Agent** | Infrastructure and Deploy | AWS (EC2), Docker, GitHub Actions | check_aws_status |

## 3. Communication Protocol (Handoff)

The handoff protocol follows `.context/03_agentic_workflow.md` as the authoritative source.

### Sequence within CrewAI

1. The **PM** executes the bootstrap (`.context/README.md`) and generates a `Feature Specification`.
2. The **Backend** consumes the Spec and generates `API Contract/Code`.
3. The **Frontend** consumes the `API Contract` and generates `UI Components`.
4. The **QA** validates against the gates in `.context/05_quality_and_gates.md`.
5. The **DevOps** executes deployment with human approval.

### Handoff between sessions

When a block does not finish in the same session, record in `.context/handoffs/`
using `templates/handoff_template.md`.

Full reference: `.context/03_agentic_workflow.md`, section "Contrato de handoff".

## 4. Security Rules and Guardrails

- **No secrets in files:** Agents must never write API keys or passwords to files.
  Use environment variables exclusively.
- **Human validation:** Deploy tasks (`DevOps`) must have `human_input=True` for
  final approval before touching AWS infrastructure.
- **Path-validated writes:** All file writes go through `validate_write_path()` which
  enforces an allowlist of writable directories and blocks protected files.
  See `tools/tool_security.py` for the full security specification.
- **Selective git staging:** The `git_operations` tool never uses `git add .`.
  It filters files against `GIT_STAGE_BLOCKLIST` before staging.
- **Conventional branching:** Branch names must start with a valid prefix
  (feat/, fix/, refactor/, chore/, docs/, test/, perf/, security/).
- **Audit logging:** Every tool invocation is logged to `ai_squad/logs/tool_audit.log`.

## 5. Tools Registry

Tools are centralized in `tools/project_tools.py` with security primitives in
`tools/tool_security.py`. All agents use the same validated methods for file system
interaction, subprocess execution, and git operations.

| Category | Tools | Description |
| :--- | :--- | :--- |
| **Read** | read_tasks, read_schema, read_context_file, read_governance_file | Safe read-only access to project files |
| **Write** | write_file_content | Path-validated file writes (allowlist + denylist) |
| **Execution** | run_backend_tests | Timeout-enforced pytest execution |
| **Infrastructure** | check_aws_status | AWS EC2 status check (read-only) |
| **Git** | git_operations | Branch creation, selective commit, status |
