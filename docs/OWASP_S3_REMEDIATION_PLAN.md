# OWASP S3 - Prioritized Remediation Plan

Updated at: 2026-02-11
Order enforced by product: `S3 -> S2 -> S1`.

## Objective
Convert S3 findings into an execution-ready remediation sequence with priorities, acceptance criteria, and destination streams (`S2` app controls, `S1` infra controls).

## Priority Scale
- P0: critical risk, immediate mitigation.
- P1: high risk, implement in current cycle.
- P2: medium risk, schedule next cycle.

## Remediation Backlog

| Priority | Track | Control | OWASP refs | Current status | Acceptance criteria |
|---|---|---|---|---|---|
| P0 | S2 | Global rate limiting for REST auth + transaction + wallet endpoints | API4, API6 | Not implemented | Limits enforced per IP/user, 429 responses standardized, tests added |
| P0 | S2 | GraphQL transport protection (depth + complexity + operation cost cap) | API4, API8 | Not implemented | Queries above threshold blocked, error contract defined, tests added |
| P0 | S2 | Sensitive flow abuse controls (login/register/createTransaction) | API2, API6 | Partial | Burst abuse blocked, lock/throttle strategy documented and tested |
| P1 | S2 | Input sanitization/normalization policy for free-text fields | API3, API10 | Partial | Central sanitization policy implemented and tested |
| P1 | S2 | Authorization matrix + negative tests for object/function access | API1, API5 | Partial | Matrix documented, tests cover cross-user access denial |
| P1 | S1 | EC2 hardening baseline (SG/NACL/IMDSv2/SSH policy/patching) | API8, ASVS V14 | Partial | Checklist applied on DEV+PROD with auditable evidence |
| P1 | S1 | Secrets lifecycle and rotation policy | API2, ASVS V8 | Partial | Rotation runbook + schedule + validation evidence |
| P2 | S2 | External API trust policy (BRAPI response validation and failure policy) | API10 | Partial | Validation contract and fallback policy enforced |
| P2 | S1 | Security monitoring evidence (TLS expiry, auth anomalies, 4xx/5xx spikes) | API8, API9 | Partial | Alerts and dashboards defined with ownership |

## Milestone Plan

### Milestone A (Immediate)
- Deliver P0 items in S2.
- Produce CI evidence showing controls active.

### Milestone B (Hardening)
- Deliver P1 items across S2 and S1.
- Publish runbooks and validation artifacts.

### Milestone C (Maturity)
- Deliver P2 items.
- Reassess OWASP checklist and update statuses.

## Evidence Requirements
Each remediation item must include:
1. code/config change reference;
2. automated test or CI assertion;
3. operational verification note for DEV and PROD;
4. update in `TASKS.md` with commit linkage.
