# OWASP S3 - Attack Surface Inventory

Updated at: 2026-02-11
Scope: `/app/controllers/*`, `/app/graphql/*`, auth middleware and runtime exposure.

## Objective
Create the security inventory required by `S3` as input for remediation tasks in the defined execution order:
- `S3` (OWASP baseline/checklist)
- `S2` (application security controls)
- `S1` (AWS infra hardening)

## Public Entry Points
- REST base routes:
  - `/auth/*`
  - `/user/*`
  - `/transactions/*`
  - `/wallet/*`
  - `/graphql`
  - `/docs/*`
- GraphQL: single endpoint `POST /graphql` with mixed public/private operations.

## REST Endpoint Matrix

| Surface | Method | Path | Auth | Main data/actions | OWASP risk focus |
|---|---|---|---|---|---|
| Auth | POST | `/auth/register` | Public | User creation | API2, API10 |
| Auth | POST | `/auth/login` | Public | Credential auth / JWT issue | API2, API4 |
| Auth | POST | `/auth/logout` | JWT | Session/token invalidation | API2 |
| User | PUT | `/user/profile` | JWT | Personal/financial profile update | API1, API3, API5 |
| User | GET | `/user/me` | JWT | Consolidated user+transactions+wallet view | API1, API3 |
| Transactions | POST | `/transactions` | JWT | Create transaction(s), installment flows | API4, API6 |
| Transactions | PUT | `/transactions/{transaction_id}` | JWT | Update transaction | API1, API3 |
| Transactions | DELETE | `/transactions/{transaction_id}` | JWT | Soft delete transaction | API1, API5 |
| Transactions | PATCH | `/transactions/restore/{transaction_id}` | JWT | Restore soft-deleted transaction | API1, API5 |
| Transactions | GET | `/transactions/deleted` | JWT | List deleted transactions | API1 |
| Transactions | DELETE | `/transactions/{transaction_id}/force` | JWT | Hard delete transaction | API1, API5 |
| Transactions | GET | `/transactions/summary` | JWT | Monthly summary | API1 |
| Transactions | GET | `/transactions/dashboard` | JWT | Monthly dashboard aggregates | API1 |
| Transactions | GET | `/transactions/list` | JWT | Active list with filters | API1, API4 |
| Transactions | GET | `/transactions/expenses` | JWT | Period expense list + metrics | API1, API4 |
| Wallet | POST | `/wallet` | JWT | Create wallet entry | API1, API3 |
| Wallet | GET | `/wallet` | JWT | List wallet entries | API1 |
| Wallet | GET | `/wallet/{investment_id}/history` | JWT | Wallet history | API1 |
| Wallet | POST | `/wallet/{investment_id}/operations` | JWT | Add investment operation | API1, API4, API6 |
| Wallet | GET | `/wallet/{investment_id}/operations` | JWT | List operations | API1 |
| Wallet | PUT | `/wallet/{investment_id}/operations/{operation_id}` | JWT | Update operation | API1, API3 |
| Wallet | DELETE | `/wallet/{investment_id}/operations/{operation_id}` | JWT | Delete operation | API1, API5 |
| Wallet | GET | `/wallet/{investment_id}/operations/summary` | JWT | Operation summary | API1 |
| Wallet | GET | `/wallet/{investment_id}/operations/position` | JWT | Position/cost basis | API1 |
| Wallet | GET | `/wallet/{investment_id}/operations/invested-amount` | JWT | Amount by date | API1 |
| Wallet | GET | `/wallet/valuation` | JWT | Portfolio valuation | API1, API10 |
| Wallet | GET | `/wallet/valuation/history` | JWT | Portfolio history valuation | API1, API10 |
| Wallet | GET | `/wallet/{investment_id}/valuation` | JWT | Asset valuation | API1, API10 |
| Wallet | PUT | `/wallet/{investment_id}` | JWT | Update wallet entry | API1, API3 |
| Wallet | DELETE | `/wallet/{investment_id}` | JWT | Delete wallet entry | API1, API5 |
| GraphQL transport | POST | `/graphql` | Mixed | Public + private operations multiplexed | API4, API8, API9 |

## GraphQL Operation Matrix

### Public GraphQL mutations
| Operation | Auth | OWASP focus |
|---|---|---|
| `registerUser` | Public | API2, API10 |
| `login` | Public | API2, API4 |

### Authenticated GraphQL queries
| Operation | Auth | OWASP focus |
|---|---|---|
| `me` | JWT | API1, API3 |
| `transactions` | JWT | API1, API4 |
| `transactionSummary` | JWT | API1 |
| `transactionDashboard` | JWT | API1 |
| `walletEntries` | JWT | API1 |
| `walletHistory` | JWT | API1 |
| `investmentOperations` | JWT | API1 |
| `investmentOperationSummary` | JWT | API1 |
| `investmentPosition` | JWT | API1 |
| `investmentInvestedAmount` | JWT | API1 |
| `investmentValuation` | JWT | API1, API10 |
| `portfolioValuation` | JWT | API1, API10 |
| `portfolioValuationHistory` | JWT | API1, API10 |
| `tickers` | JWT | API1 |

### Authenticated GraphQL mutations
| Operation | Auth | OWASP focus |
|---|---|---|
| `logout` | JWT | API2 |
| `updateUserProfile` | JWT | API1, API3 |
| `createTransaction` | JWT | API4, API6 |
| `deleteTransaction` | JWT | API1, API5 |
| `addWalletEntry` | JWT | API1, API3 |
| `updateWalletEntry` | JWT | API1, API3 |
| `deleteWalletEntry` | JWT | API1, API5 |
| `addInvestmentOperation` | JWT | API1, API4, API6 |
| `updateInvestmentOperation` | JWT | API1, API3 |
| `deleteInvestmentOperation` | JWT | API1, API5 |
| `addTicker` | JWT | API1, API3 |
| `deleteTicker` | JWT | API1, API5 |

## Current Security Controls Snapshot
- JWT required in most REST protected routes.
- GraphQL private operations protected via resolver-level `get_current_user_required()`.
- Global auth guard with open endpoint list for public surfaces.
- Rate-limit baseline enabled for `/auth`, `/graphql`, `/transactions` and `/wallet`.
- GraphQL transport now enforces query-size, depth, complexity and operation-count limits.
- Schema validation present in multiple flows (Marshmallow/webargs).
- TLS enabled at Nginx layer for internet-facing domains.

## Gaps Identified (to drive S2/S1)
1. GraphQL cost model is generic and still needs domain-specific weighting (`API4`, `API8`).
2. No standardized request sanitization policy for free-text fields (`API3`, `API10`).
3. Open endpoint handling is string-based and requires hardening tests (`API5`, `API8`).
4. No formal inventory ownership metadata tied to CI evidence (`API9`).
5. Rate-limit state is in-memory only (needs distributed strategy for multi-instance scale).

## Immediate Backlog Handoff
- S3.2: convert this inventory into a control checklist with pass/fail evidence fields.
- S2.2: evoluir custo de GraphQL para ponderação por campo sensível e domínio.
- S2.3: enforce sanitization/normalization policy in request parsing layer.
- S2.4: evolve rate-limit from in-memory to distributed storage (Redis or equivalent).
- S1.1: align EC2 SG/NACL/IMDSv2 checks with exposed surfaces in this inventory.
