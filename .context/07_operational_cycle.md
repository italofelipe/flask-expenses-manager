# Operational Cycle — Multi-Agent Feature Delivery

## Purpose

This document defines the end-to-end cycle for delivering features in the
Auraxis project using multiple AI agents. It is the authoritative reference
for how work flows from a human idea to deployed code with feedback.

## Participants

| Role | Who | Responsibility |
|:-----|:----|:---------------|
| **Product Owner (PO)** | Italo (human) | Provides specs, approves plans, supervises, makes product decisions |
| **Claude** | Anthropic Claude | Direct implementation, review, analysis, documentation |
| **Gemini** | Google Gemini | Architecture review, orchestration analysis, alternative perspectives |
| **Gepeto** | OpenAI GPT | Implementation, code generation, problem-solving |
| **CrewAI** | ai_squad/ pipeline | Automated multi-agent pipeline (PM + Backend + QA) |

## The Cycle

### Phase 1: SPEC (PO → Agent)

**Input:** PO describes the feature in natural language.
**Output:** Formalized feature card in TASKS.md.

The PO provides any combination of:
- Problem description
- Acceptance criteria
- Expected behavior
- Constraints or preferences
- Test data expectations

The PO does NOT need to be technical. The first agent to receive the
briefing is responsible for formalizing it.

**Agent action:**
1. Read the PO's briefing.
2. Read `.context/04_architecture_snapshot.md` to understand current state.
3. Create a feature card using `templates/feature_card_template.md`.
4. Fill: Context, Acceptance criteria, Impact on existing code.
5. Present the card to PO for approval.

**Gate:** PO approves the card before any code is written.

---

### Phase 2: ANALYSIS (Agent)

**Input:** Approved feature card.
**Output:** Completed feature card with risks, gaps, and opportunities.

**Agent action:**
1. Read related source files to understand current implementation.
2. Identify risks (what can break), gaps (what's missing), and
   opportunities (improvements that come naturally with this change).
3. Fill the "Risks and dependencies" section of the card.
4. If the feature is complex (size L or XL), create a detailed spec
   using `templates/feature_spec_template.md` in `docs/specs/FEAT-XXX.md`.
5. Present findings to PO.

**Gate:** PO confirms risk assessment. Agent proceeds only if PO agrees
with the identified risks and trade-offs.

---

### Phase 3: REFINEMENT (PO + Agent)

**Input:** Card with analysis.
**Output:** Card with task breakdown and validation commands.

**Agent action:**
1. Break the feature into small, incremental tasks (1 task = 1 commit).
2. Each task gets a "Validation" command — a runnable check that proves
   the task works independently before moving to the next.
3. Define the branch name following conventional branching.
4. Fill "Tasks breakdown" in the feature card.
5. Present to PO for final approval.

**Gate:** PO approves the task breakdown. This is the last approval
before autonomous execution begins.

---

### Phase 4: EXECUTION (Agent, autonomous)

**Input:** Approved task breakdown.
**Output:** Working code, tests, passing quality gates.

**Agent action:**
1. Create branch: `feat/xxx-description`.
2. For each task in order:
   a. Implement the code change.
   b. Write/update tests.
   c. Run the task's validation command.
   d. If validation passes → commit (conventional commit format).
   e. If validation fails → fix and re-validate before committing.
   f. Update task status in the card (⚪ → 🟢).
3. After all tasks:
   a. Run full quality gates (black, isort, flake8, mypy, pytest).
   b. Verify coverage >= 85%.
4. PO supervises in parallel (reads commits, asks questions if needed).

**Rules during execution:**
- One commit per task (granular, rollback-safe).
- Never skip quality gates.
- Never commit directly to master.
- If blocked, create a handoff using `templates/handoff_template.md`
  and notify PO instead of guessing.

---

### Phase 5: DELIVERY + FEEDBACK (Agent → PO)

**Input:** All tasks done, quality gates passing.
**Output:** Delivery report + updated TASKS.md.

**Agent action:**
1. Create delivery report using `templates/delivery_report_template.md`.
   Save to `.context/reports/FEAT-XXX_delivery.md`.
2. The report must include:
   - What was delivered (summary for humans).
   - What went well.
   - What was difficult or unexpected.
   - Attention points for PO.
   - Technical debt generated (mandatory — "None" if clean).
   - Recommendations for next step.
3. Update TASKS.md:
   - Feature card status → Done.
   - Technical debt items → added to backlog as future tasks.
4. Present the delivery report to PO.

**Gate:** PO reviews delivery report and confirms acceptance.

---

### Phase 6: CLOSE (PO)

**Input:** Delivery report.
**Output:** Feature officially closed.

PO actions:
- Reviews the delivery report.
- Manually tests if desired.
- Approves or requests adjustments.
- Decides on technical debt priority.
- Signals readiness for next feature.

---

## Cross-Agent Conventions

### How agents identify themselves

Every agent MUST sign their work:
- **In commits:** Include agent name in commit body or co-author tag.
- **In feature cards:** Fill "Assigned agent" field.
- **In delivery reports:** Fill "Delivered by" field.
- **In handoffs:** State who is handing off and who should pick up.

### How agents hand off to each other

When one agent cannot finish (context limit, session end, wrong expertise):
1. Create handoff using `templates/handoff_template.md`.
2. Save to `.context/handoffs/FEAT-XXX_handoff_YYYY-MM-DD.md`.
3. Update the feature card: status → in_progress, add note about handoff.
4. The next agent reads the handoff BEFORE resuming work.

### How agents resolve conflicts

If two agents have different opinions on implementation:
1. Both document their position (in the feature card or spec).
2. PO decides. Agent preferences do not override PO decisions.
3. The chosen approach is recorded. The rejected approach is noted
   as "considered alternative" for future reference.

### What agents must NEVER do without PO approval

- Change product scope (add/remove acceptance criteria).
- Delete existing code or tests.
- Modify governance files (steering.md, product.md, .context/01-06).
- Skip quality gates.
- Deploy to any environment.
- Make architecture decisions with cross-cutting impact.

---

## File Map

| Artifact | Location | Created by |
|:---------|:---------|:-----------|
| Feature card | TASKS.md (inline) | Agent (from PO briefing) |
| Feature spec (detailed) | docs/specs/FEAT-XXX.md | Agent (for L/XL features) |
| Delivery report | .context/reports/FEAT-XXX_delivery.md | Delivering agent |
| Handoff | .context/handoffs/FEAT-XXX_handoff_DATE.md | Agent stopping work |
| Quality gates reference | .context/05_quality_and_gates.md | Maintained by team |
| Architecture snapshot | .context/04_architecture_snapshot.md | Maintained by team |

---

## Quick Start for New Agents

If you are an AI agent reading this for the first time:

1. Read `.context/README.md` → understand the knowledge base.
2. Read `.context/01_sources_of_truth.md` → understand document hierarchy.
3. Read this file → understand the delivery cycle.
4. Read `TASKS.md` → find what needs to be done.
5. Read `.context/04_architecture_snapshot.md` → understand the codebase.
6. Read `steering.md` → understand execution rules.
7. Read `product.md` → understand product direction.
8. Check `.context/handoffs/` → see if someone left work for you.
9. Pick the next priority feature and begin Phase 1.
