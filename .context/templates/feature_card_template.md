# Feature Card Template

<!--
PURPOSE:
This is the operational card that goes into TASKS.md for each feature.
It is the contract between the Product Owner and all AI agents (Claude,
Gemini, Gepeto/GPT) working on the Auraxis project.

WHO WRITES THIS: The Product Owner provides the spec in natural language.
The first agent to pick up the feature formalizes it into this card and
submits for PO approval before any code is written.

WHO READS THIS: All agents (Claude, Gemini, Gepeto, CrewAI pipeline).
This card must be self-contained — an agent starting a fresh session
should be able to understand the feature from this card alone, combined
with the .context/ knowledge base.

RELATIONSHIP WITH OTHER TEMPLATES:
- feature_spec_template.md → detailed technical spec (contracts, models,
  errors). Created AFTER this card is approved. Lives in docs/specs/.
- handoff_template.md → used when work is interrupted mid-feature.
- delivery_report_template.md → used after feature is delivered.

RULES:
- Keep language neutral (English preferred for multi-agent compatibility).
- All fields are mandatory unless marked (optional).
- Acceptance criteria must be checkboxes (parseable by agents).
- "Validation per task" must have runnable commands.
- Do NOT duplicate the full technical spec here — reference it.

LIFECYCLE:
1. PO gives natural language spec → Agent creates this card → PO approves
2. Agent creates detailed spec (feature_spec_template.md) if needed
3. Agent breaks into tasks, implements, tests
4. Agent creates delivery report (delivery_report_template.md)
5. Card status updated to Done in TASKS.md
-->

## [FEAT-XXX] Feature Title

**Status:** backlog | in_progress | blocked | done
**Priority:** P0 | P1 | P2
**Size:** S | M | L | XL
**Assigned agent:** Claude | Gemini | Gepeto | CrewAI | unassigned
**Branch:** (filled when work starts)
**Spec:** (link to docs/specs/FEAT-XXX.md when created)

### Context

What problem does this solve? Why now? Who benefits?

(2-4 sentences. Written by PO or formalized by agent from PO's briefing.)

### Acceptance criteria

- [ ] AC1: (specific, testable behavior)
- [ ] AC2: (specific, testable behavior)
- [ ] AC3: (specific, testable behavior)

### Impact on existing code

<!--
MANDATORY — agent must fill this BEFORE starting implementation.
Lists every file/contract that will change, and what breaks if done wrong.
This is the PO's safety net for approving the plan.
-->

| Area | Impact | Risk if wrong |
|:-----|:-------|:--------------|
| Models | (e.g., new model X, alter model Y) | (e.g., migration breaks existing data) |
| GraphQL | (e.g., new query, mutation changed) | (e.g., frontend contract broken) |
| REST | (e.g., new endpoint, response changed) | (e.g., existing clients break) |
| Services | (e.g., new service, logic moved) | (e.g., side effect on related feature) |
| Tests | (e.g., new test file, existing tests affected) | (e.g., coverage drops below 85%) |

### Expected test data

<!--
Describe realistic seed data that exercises the feature.
Agents use this to create fixtures/factories during implementation.
-->

- (e.g., 5 categories: Food, Transport, Housing, Health, Leisure)
- (e.g., 50 transactions distributed across categories)
- (e.g., 1 test user with 3 months of history)

### Tasks breakdown

<!--
Filled by the agent after PO approves the card.
Each task must have a validation command that proves it works independently.
Order matters — tasks are executed top to bottom.
-->

| # | Task | Validation | Status |
|:--|:-----|:-----------|:------:|
| 1 | (e.g., Create Category model + migration) | `pytest tests/test_category_model.py -v` | ⚪ |
| 2 | (e.g., Create CategorySchema) | `pytest tests/test_category_schema.py -v` | ⚪ |
| 3 | (e.g., Create CategoryService) | `pytest tests/test_category_service.py -v` | ⚪ |
| 4 | (e.g., Create GraphQL resolver) | `pytest tests/test_category_graphql.py -v` | ⚪ |
| 5 | (e.g., Run full quality gates) | `black . && isort . && flake8 . && mypy app && pytest` | ⚪ |

### Risks and dependencies

- **Risk:** (what could go wrong)
- **Mitigation:** (what to do about it)
- **Dependency:** (optional — blocked by what?)

### Technical debt allowance

<!--
Optional — if the PO explicitly accepts shortcuts for speed.
Must be registered in TASKS.md as future debt after delivery.
If empty, agent must deliver at full quality.
-->

- (e.g., "Skip integration tests for now, unit tests sufficient for V1")
- (e.g., "Hardcode enum values, make configurable in V2")

---

<!--
AGENT INSTRUCTIONS:
1. Copy this template into the appropriate section of TASKS.md.
2. Replace [FEAT-XXX] with the next available feature ID.
3. Fill "Context" and "Acceptance criteria" from PO's briefing.
4. Fill "Impact on existing code" by reading the codebase.
5. Present the card to PO for approval BEFORE writing any code.
6. After approval, fill "Tasks breakdown" and begin implementation.
7. After delivery, create a delivery report using delivery_report_template.md.
-->
