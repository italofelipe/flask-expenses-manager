# Archived configs

## `github_master_ruleset.json`

**Archived 2026-05-27** via PR closing issue #1374.

Original purpose: target ruleset for `.github/workflows/governance.yml` to audit/sync via the GitHub API. The workflow + config were the automated enforcement of branch protection.

**Why archived:**
- Config required `required_approving_review_count: 1` and 10 status checks, incompatible with the solo-dev posture documented in the user's memory (`feedback_solo_dev_no_review_required`, `feedback_pr_approval_removed`).
- Workflow had 0% success for 30+ days (PAT `TOKEN_GITHUB_ADMIN` expired).
- Branch protection is now managed manually via GitHub UI — appropriate for 1-developer project.

If branch governance automation becomes needed again, this file is a starting point:
1. Update `required_approving_review_count` to match desired posture (0 for solo dev).
2. Update `required_status_checks` list to match current CI workflows (Tests, Quality, Secret Scan, Container Security, Dependency Review, OSV).
3. Recreate `scripts/github_ruleset_manager.py` workflow with a fresh PAT.
