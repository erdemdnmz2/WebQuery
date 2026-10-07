# Remaining implementation plan

This is the single backlog replacing duplicate legacy plans. Nothing below was
silently implemented during repository cleanup. Each behavior/schema/security
change needs its own feature spec, ADR where appropriate, and regression tests.
The order favors correctness and deployment evidence over new product scope.

## P0 — Establish the new repository's evidence

- Run the first PR through backend, frontend, MSSQL and CodeQL. Verify action
  allowlist compatibility; configure required checks only after actual runs.
- Read-only API verification on 2026-10-07 reports `allowed_actions=all`, not the
  earlier intended selected-action allowlist. Read-only token/default PR approval
  settings are correct. Review the UI/account scope and restore the allowlist
  separately with maintainer approval; this cleanup did not change settings.
- Preserve the merged main fixes (`1b5dfdf` SQL Server boolean filtering and
  `5c77bea` owner lookup result closure). Do not restore the stale hardening
  branch wholesale or repeat those fixes as unfinished work.
- Acceptance: local packaging/source checks pass; a new-repo PR has real green
  job results. No claim of remote success before those results exist.

## P1 — Align cancellation with the earlier outage decision

- Evidence: `ExecutionRegistry.track()` skips ID-less requests; cancel requires
  Redis. SPEC-0032 records current compatibility; OQ-2026-021 requires all new
  work fail closed and local active handles remain cancellable during outage.
- Write a reconciliation spec that preserves that decision; do not silently
  make `execution_id` mandatory and break old clients. Compare server-generated
  IDs and a staged client contract before choosing the durable design.
- Acceptance: no execution begins without registration when Redis is down;
  already-active local work can still be cancelled safely; cross-user requests
  remain hidden; cancellation/commit races and connection reuse remain correct.
- Tests: outage before registration, outage during active SQL, old clients,
  multiple workers, commit seal and real-driver rollback/pool reuse.

## P2 — Separate bootstrap secrets and prove deployment safety

- Evidence: Compose interpolates raw credential strings, shares app/SA password,
  defaults to a broad proxy CIDR, exposes HTTP 80 and uses mutable image tags.
- Spec/ADR: separate bootstrap/migration privileges from runtime credentials;
  use an encoded URL construction contract. Remove the need for runtime SA
  access only with an explicit provision/migration workflow.
- Acceptance: passwords with reserved URL characters round-trip; no runtime SA
  secret; TLS terminates on the private ingress; only measured proxy peers are
  trusted; metadata/Redis remain unexposed; artifacts are versioned.
- Tests: bootstrap idempotency, non-privileged runtime startup, forwarded-header
  spoof rejection, reachability probes and image/secret review.
- Follow with a **sanitized staging** backup/restore + Alembic upgrade rehearsal:
  preexisting encrypted rows, indexes/constraints, UUID/NVARCHAR types, OWNER,
  login, query and cancellation after restore. Never use a customer database in CI.

## P3 — Remove legacy central credential fallback

- Evidence: `DatabaseProvider._credentials_for()` permits `ro`/`rw` central
  credentials when no tier credentials exist; startup still requires them.
- Inventory legacy registrations without revealing credential values. Migrate
  them to real DBA-provisioned tier accounts before removing the fallback/guard
  requirements. Missing tiers must not silently elevate privileges.
- Acceptance/tests: no central target runtime path; missing/partial tiers fail
  closed; public catalogues never contain credentials; tier isolation and pool
  invalidation survive rotation. Avoid conflating this with metadata bootstrap.

## P4 — Harden encryption and masking guarantees

- Evidence: `EncryptedText.process_result_value()` returns raw stored text on
  decrypt failure; table-aware masking uses result column names, not full lineage.
- Split into two reviewed specs: legacy plaintext migration followed by
  fail-closed decrypt errors; and a defined masking contract for aliases, joins,
  schema collisions and expressions. Do not claim arbitrary SQL masking is safe.
- Acceptance/tests: missing/wrong/retired keys never flow as usable credentials;
  rotation covers all encrypted fields and verified backups; alias/join cases
  cannot expose columns promised as masked. Retain target DB least privilege.

## P5 — Simplify the role mirror, then target identity storage

- Source-worktree ADR-0022 accepts removing the persisted `is_admin` mirror.
  It is not implemented at the imported commit. Remove the column, event and
  manual writes with a new Alembic revision and matching schema guard; retain
  API `is_admin` derived from `role`. Test ORM/direct-write authority and MSSQL
  upgrade. Do not rewrite old migrations or drop the table as routine cleanup.
- Separate feature/ADR: admin UUID resource contract and saved-query target FK.
  `Databases` name fields are 100 chars while `QueryData` uses 50; UUIDs are
  indexed but not universally unique. Plan deduplication/backfill before new
  constraints; keep rename, soft-delete and audit semantics intact.
- Acceptance/tests: old data migrates without ambiguity; no orphaned workspaces;
  long names persist; uniqueness is enforced; intentional ID compatibility holds.

## P6 — Fill test gaps before broad refactoring

- Port frontend behavioral tests selectively; the Vitest commit exists on another
  branch but is absent from main. Specify runner/dependencies/CI in a dedicated
  change, not by merging unrelated hardening changes.
- Cover session refresh retries, cancellation states on Studio/RunWorkspace/
  preview, role/capability display, masking indicators and database edit conflicts.
- Add real PostgreSQL/MySQL cancellation/transaction/pool-reuse coverage using
  the existing least-privilege tier accounts, not privileged control accounts.
- Reassess multi-worker query limits: login is Redis-shared but SlowAPI execution
  limits are process-local. Document intended limits before changing the boundary.
- Acceptance: these are actual behavioral/live-driver tests, not substitutes
  consisting only of typecheck, contrast scripts or SQLite mocks.

## P7 — Optimize based on measurements

- Profile editor bundle loading, target pool saturation and Redis polling under
  concurrent queries. Establish budgets before code splitting/cache changes.
- Investigate capped-read warning semantics (`MAX_ROW_COUNT_WARNING` exceeds the
  returned-row cap) and buffered mixed/write-result batches. Keep API contracts
  explicit; do not equate response row caps with a universal memory bound.
- Acceptance: before/after timing/memory data plus unchanged authorization,
  audit, masking and cancellation behavior.

## Deferred product work — not blockers for a portfolio baseline

- Customer-isolated deployment inside each customer's VPN is the accepted
  source-worktree direction (ADR-0023 / SPEC-0028), not a delivered deployment
  system or a shared multi-tenant SaaS. Prepare one reproducible private-network
  release template after P2; do not add billing/tenant scope without a new request.
- Complete multi-result-set and per-statement affected-row reporting only after
  its API/UI contract is selected. Current batch response is not a full report.
- Destructive-DML confirmation remains deferred by OQ-2026-010 until meaningful
  impact/row-count design exists; do not add a generic checkbox as a cleanup.
- Navbar running-query management remains deferred; current cancellation is
  per executing surface and owner scoped.
