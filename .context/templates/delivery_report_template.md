# Delivery Report Template

<!--
PURPOSE:
This report is created by the delivering agent AFTER a feature is complete.
It closes the feedback loop: PO knows what was delivered, what to watch,
and what debt was generated.

WHO WRITES THIS: The agent that implemented the feature.
WHO READS THIS: The Product Owner + any agent that works on related features.

WHEN: After all tasks in the feature card are done and quality gates pass.

WHERE TO SAVE: .context/reports/FEAT-XXX_delivery.md
(Create the reports/ directory if it doesn't exist.)

RULES:
- Be honest about what was NOT delivered or was simplified.
- "Technical debt generated" is mandatory — if there is none, write "None".
- "Attention points" are things the PO should manually verify or monitor.
- Commit hashes must be real (no placeholders).
- This report is the agent's professional accountability artifact.
-->

## Delivery Report: [FEAT-XXX] Feature Title

**Delivered by:** Claude | Gemini | Gepeto | CrewAI
**Date:** YYYY-MM-DD
**Branch:** feat/xxx-description
**Status:** delivered | partial | rolled_back

---

### 1. What was delivered

<!--
Brief summary of what the PO now has that they didn't have before.
Written for a human, not for another agent. 2-5 sentences.
-->

(Summary here)

### 2. Commits

| # | Hash | Message | Files changed |
|:--|:-----|:--------|:--------------|
| 1 | `abc1234` | `feat(scope): description` | `app/models/x.py`, `tests/test_x.py` |
| 2 | `def5678` | `test(scope): description` | `tests/test_x.py` |

### 3. Acceptance criteria verification

| AC | Description | Result | Evidence |
|:---|:------------|:------:|:---------|
| AC1 | (from feature card) | PASS / FAIL | (test name or manual check) |
| AC2 | (from feature card) | PASS / FAIL | (test name or manual check) |
| AC3 | (from feature card) | PASS / FAIL | (test name or manual check) |

### 4. Quality gates

| Gate | Result | Notes |
|:-----|:------:|:------|
| black | PASS / FAIL | |
| isort | PASS / FAIL | |
| flake8 | PASS / FAIL | |
| mypy | PASS / FAIL | |
| pytest (coverage) | PASS / FAIL | Coverage: XX% |
| pre-commit | PASS / FAIL | |

### 5. What went well

- (e.g., "Existing service pattern was easy to follow")
- (e.g., "Test coverage naturally reached 92%")

### 6. What was difficult or unexpected

- (e.g., "Migration conflicted with existing index")
- (e.g., "GraphQL resolver needed custom error handling not in spec")

### 7. Attention points for PO

<!--
Things the PO should watch, test manually, or be aware of.
Not bugs — just areas where human judgment adds value.
-->

- (e.g., "The enum values are hardcoded — if business adds new types, code change needed")
- (e.g., "Performance not tested with >1000 records — could be slow at scale")

### 8. Technical debt generated

<!--
MANDATORY — if no debt, write "None."
Each debt item becomes a candidate task in TASKS.md.
The PO decides when (or if) to pay it.
-->

| Debt | Severity | Suggested resolution |
|:-----|:--------:|:---------------------|
| (e.g., "No integration test for GraphQL mutation") | low / medium / high | (e.g., "Add in next testing cycle") |
| None | — | — |

### 9. Recommendations for next step

<!--
What the PO or next agent should consider doing after this delivery.
-->

- (e.g., "Ready to start FEAT-043 which depends on this")
- (e.g., "Consider adding admin UI for managing categories")

---

<!--
AGENT INSTRUCTIONS:
1. Copy this template to .context/reports/FEAT-XXX_delivery.md
2. Fill all sections honestly and completely.
3. Update TASKS.md: set feature card status to Done.
4. If debt was generated, add debt items to TASKS.md backlog.
5. If a handoff is needed (you can't finish), use handoff_template.md instead.
-->
