# Auraxis Coding Standards for AI Agents

## Authoritative References

For the full technology stack, architecture, and folder structure, see:
- `.context/04_architecture_snapshot.md` — codebase structure and tech stack
- `steering.md` — execution governance, branching, and quality gates
- `.context/05_quality_and_gates.md` — quality gates and Definition of Done

This document only defines rules **specific to AI agent code generation**
that are not covered in the references above.

## Agent-Specific Rules

1. Every new Model must have a corresponding Marshmallow Schema in `app/schemas/`.
2. Every new feature must include test files in `tests/`.
3. Never delete existing code without explicit permission in TASKS.md.
4. Use Type Hints in all new functions (enforced by mypy strict mode).
5. Every migration must be reversible (include downgrade logic).

## Naming Conventions

| Element | Convention | Example |
| :--- | :--- | :--- |
| Files | snake_case.py | `financial_goal.py` |
| Classes | PascalCase | `FinancialGoal` |
| Functions/Variables | snake_case | `calculate_progress()` |
| Database Tables | Plural snake_case | `financial_goals` |
| Branches | tipo/escopo-descricao | `feat/goal-simulation-endpoint` |
| Commits | Conventional Commits | `feat(goal): add simulation endpoint` |
