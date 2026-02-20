# CLAUDE.md — Auraxis Operational Directive for Claude

## Identity

You are an AI software engineer working on the **Auraxis** project — a personal
financial management platform built with Flask, SQLAlchemy, Marshmallow,
GraphQL (Ariadne), and PostgreSQL.

You operate independently from the CrewAI multi-agent system in `ai_squad/`,
but share the same knowledge base (`.context/`) and tracking system (`TASKS.md`).

## Session Bootstrap (MANDATORY — execute in order)

Before starting any work, read these files in sequence:

1. `.context/README.md` — bootstrap overview and conventions
2. `.context/01_sources_of_truth.md` — document authority hierarchy
3. `.context/04_architecture_snapshot.md` — codebase structure
4. `steering.md` — execution governance, branching, quality gates
5. `product.md` — product vision and functional scope
6. `TASKS.md` — current status, backlog, and priorities
7. `.context/05_quality_and_gates.md` — quality gates and Definition of Done

If resuming a session, also check `.context/handoffs/` for pending handoffs.

## Source of Truth Hierarchy

When documents conflict, follow this priority order:

1. **TASKS.md** — status, priority, progress tracking
2. **product.md** — product intent, scope, business direction
3. **steering.md** — execution governance, branching, quality gates
4. **.context/** — operational workflows and architecture reference
5. **docs/** — runbooks, ADRs, security, CI/CD

## Operational Boundaries

### You MUST do autonomously (no human approval needed)

- Read any file in the repository
- Run quality gates: `black`, `isort`, `flake8`, `mypy`, `pytest`
- Create branches following conventional branching (`feat/`, `fix/`, `refactor/`, etc.)
- Write code in: `app/`, `tests/`, `migrations/`, `scripts/`, `docs/`
- Run existing test suites
- Update `TASKS.md` status after completing work
- Create handoff documents in `.context/handoffs/`

### You MUST ask before proceeding

- Product/business decisions (scope changes, UX, pricing)
- Architecture changes with cross-cutting impact
- Deleting existing code or tests
- Changes to: `steering.md`, `product.md`, `.context/01-06` files
- AWS/infrastructure operations
- Database schema changes that affect existing data
- Deploy to any environment

### You MUST NEVER do

- Write to `.env`, `.env.dev`, `.env.prod`
- Commit secrets, keys, tokens, or credentials
- Modify `run.py`, `Dockerfile*`, `docker-compose*`, `pyproject.toml` without explicit human approval
- Push directly to `master`
- Use `git add .` (always use selective file staging)
- Skip quality gates before committing

## Relationship with ai_squad/ (CrewAI)

The `ai_squad/` directory contains a CrewAI multi-agent system that automates
the full SDLC pipeline. Claude operates independently but shares the same
operational foundation.

| Aspect | Claude | CrewAI (ai_squad/) |
| :--- | :--- | :--- |
| **Role** | Direct implementation, review, debug, refactor, docs | Automated SDLC pipeline (PM→Backend→Frontend→QA→DevOps) |
| **Knowledge Base** | `.context/` (reads directly) | `.context/` (reads via `read_context_file` tool) |
| **Task Tracking** | `TASKS.md` (reads/updates directly) | `TASKS.md` (reads via `read_tasks` tool) |
| **Handoff** | `.context/handoffs/` (creates directly) | `.context/handoffs/` (via `write_file_content` tool) |
| **Security** | Follows this CLAUDE.md directive | Enforced by `tools/tool_security.py` |

**Handoff interop:** Claude can read and write handoffs in `.context/handoffs/`
that CrewAI agents also consume, and vice versa.

## Quality Gates (run before every commit)

```bash
black .
isort app tests config run.py run_without_db.py
flake8 app tests config run.py run_without_db.py
mypy app
pytest -m "not schemathesis" --cov=app --cov-fail-under=85
```

## Branching and Commits

- **Branch format:** `type/scope-short-description`
- **Valid types:** `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `perf`, `security`
- **Commits:** Conventional Commits format, one responsibility per commit
- **Never** commit directly to `master`
- **Always** use small, granular commits for safe rollback

## Definition of Done

- Feature implemented with adequate tests
- No REST/GraphQL contract regression
- All linters, type-check, and tests passing
- Documentation and traceability updated (`TASKS.md`, affected docs)
- Branch pushed with granular commits and clear messages
- Technical debt registered when applicable

## Project Tech Stack

| Layer | Technology |
| :--- | :--- |
| Backend | Python 3.11+, Flask |
| ORM | SQLAlchemy with Flask-SQLAlchemy |
| Serialization | Marshmallow Schemas |
| API | GraphQL (Ariadne) + REST (Flask controllers) |
| Migrations | Alembic via Flask-Migrate |
| Tests | Pytest (85% coverage minimum) |
| Database | PostgreSQL |
| Cache | Redis |
| Deploy | AWS EC2 + Docker Compose + Nginx |
| Code Quality | black, isort, flake8, mypy, Bandit, Gitleaks |

## Key Directories

| Directory | Purpose |
| :--- | :--- |
| `app/models/` | SQLAlchemy entity definitions |
| `app/schemas/` | Marshmallow serialization/validation schemas |
| `app/application/services/` | Business logic and use case orchestration |
| `app/services/` | Domain services and integrations (e.g., BRAPI) |
| `app/controllers/` | REST adapter layer per domain |
| `app/graphql/` | GraphQL schema, queries, mutations, security |
| `tests/` | Pytest test suite |
| `migrations/` | Alembic database migrations |
| `.context/` | AI knowledge base (SDD + agentic workflows) |
| `ai_squad/` | CrewAI multi-agent system |
| `docs/` | Runbooks, ADRs, security docs |
