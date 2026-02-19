# CD Automation Plan (AWS + GitHub Actions + SSM)

Last update: 2026-02-19

## Objective
Eliminate manual EC2 deploy operations (SSH/SSM interactive) and make deployments deterministic, auditable, and repeatable from GitHub Actions.

## Current state (as-is)
- CI is working and gated by quality/security checks.
- Deploy workflow exists at `.github/workflows/deploy.yml`.
- Deploy executor exists at `scripts/aws_deploy_i6.py` and runs commands via AWS SSM.
- OIDC role assumption is configured and functional.
- Main operational pain points:
  - Legacy repo path split (`/opt/flask_expenses` vs `/opt/auraxis`).
  - Instance-level git/bootstrap drift.
  - Manual intervention still needed during edge cases.

## Target state (to-be)
- Single deploy path on EC2: `/opt/auraxis`.
- GitHub Actions is the only deploy entrypoint.
- No SSH required for routine operations.
- Deploy with automatic smoke validation and one-click rollback.
- Distinct DEV (auto) and PROD (manual approval) promotion flow.

## Deployment strategy

### Phase 1 (stabilize current SSM CD)
Use existing SSM deploy model, remove drift and standardize runtime.

1. Standardize path and ownership on instances
- Ensure `/opt/auraxis` exists in DEV/PROD.
- If legacy path exists, migrate or symlink to `/opt/auraxis`.
- Ensure `ubuntu` owns repository directory.

2. Standardize env files and required vars
- Ensure `.env.prod` has mandatory keys for auth guard and login guard.
- Ensure domain values are correct per environment:
  - DEV: `dev.api.auraxis.com.br`
  - PROD: `api.auraxis.com.br`

3. Harden deploy workflow
- Keep OIDC role + environment protections (`dev`, `prod`).
- DEV deploy on push to `master`.
- PROD deploy only via `workflow_dispatch` + required reviewer.

4. Add smoke + rollback gates
- Post-deploy smoke checks (`/healthz`, GraphQL basic query, auth endpoint sanity).
- If smoke fails, auto-run `scripts/aws_deploy_i6.py rollback`.

5. Remove manual dependency
- Document only two operator commands for emergencies:
  - run workflow manually
  - run rollback workflow manually

### Phase 2 (recommended next: image-based CD)
Move from "git pull on EC2" to immutable Docker image deployment.

1. Build image in CI
- Build application image on each merge.
- Push to ECR with immutable tags (`sha`, `date-sha`).

2. Deploy by image tag (not git ref)
- SSM command updates compose image tag and recreates services.
- No git credentials on EC2.

3. Promotion flow
- DEV deploy on merge.
- PROD deploy by reusing tested DEV image tag.

4. Rollback flow
- Roll back by previous image tag from deploy state.

## Detailed execution backlog

## CD-01 Path normalization (DEV + PROD)
- Status: DONE
- Deliverable: `/opt/auraxis` as canonical path in both instances.
- Acceptance:
  - `test -d /opt/auraxis` passes in DEV/PROD
  - `docker compose ...` executed from `/opt/auraxis`

## CD-02 Deploy preflight check
- Status: DONE
- Deliverable: preflight in `scripts/aws_deploy_i6.py` validating:
  - repo dir exists
  - env file exists
  - required vars are present
  - docker daemon reachable
- Acceptance: deploy aborts with explicit reason before mutating runtime.

## CD-03 Automatic smoke + auto-rollback
- Status: DONE
- Deliverable: workflow step after deploy:
  - checks `/healthz`
  - checks one protected route behavior contract
  - rollback on failure
- Acceptance: failed smoke leaves environment on previous stable ref.

## CD-04 Separate deploy role permissions by environment
- Status: DONE
- Deliverable:
  - `auraxis-github-deploy-dev-role` scoped to DEV instance
  - `auraxis-github-deploy-prod-role` scoped to PROD instance
- Acceptance: principle of least privilege enforced.

## CD-05 Deploy visibility
- Status: DONE
- Deliverable:
  - workflow summary with deployed ref/tag, command id, smoke result
  - persisted deploy history (`/var/lib/auraxis/deploy_state.json` + artifact)
- Acceptance: operator can identify deployed version in < 1 minute.

## CD-06 Immutable deployment (ECR)
- Status: TODO
- Deliverable:
  - CI build + push to ECR
  - deploy script updated to consume image tag
- Acceptance:
  - no `git fetch/checkout` in deploy flow
  - rollback by previous image tag

## Operational runbook shortcuts

### Normal deploy
1. Open GitHub Actions `Deploy`.
2. Run `dev` deploy.
3. Validate smoke checks.
4. Run `prod` deploy with approval.

### Emergency rollback
1. Run workflow dispatch for rollback in target env.
2. Validate `/healthz` and core auth route.
3. Record incident in runbook timeline.

## Human actions still required (outside automation)
- AWS IAM role/policy creation and periodic review.
- Route53/domain management and TLS issuance edge cases.
- Cost/budget threshold changes.

## Risk register
- Residual drift risk if operators reintroduce ad-hoc paths outside `/opt/auraxis`.
- Runtime config risk if `.env.prod` is manually edited without validation.
- Security risk if deploy role permissions are broader than needed.

## Recommendation (priority order)
1. Start Phase 2 (CD-06) to remove git dependency on instances.
2. Keep weekly governance/audit checks for deploy role least-privilege.
3. Periodically validate rollback drill to avoid operational drift.
