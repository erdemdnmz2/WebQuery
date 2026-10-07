# Architecture and retained decisions

This describes the imported `6cf0a73` implementation, not a new architecture
approval. [Migration analysis](migration-analysis.md) maps original decision IDs.

## Runtime boundaries

React/Vite calls same-origin `/api` endpoints through the dev proxy or nginx.
FastAPI domain routers delegate to services through `dependencies.AppContext`.
`AppDatabase` stores identities, sessions, target registrations, workspaces and
audit in WebQuery's **metadata database**. It is distinct from the **target
databases** on which users execute SQL.

`DatabaseProvider` selects a target credential tier and caches engines per
database UUID/tier. `QueryAnalyzer` parses SQL once into a `QueryPlan`; shared
runner, risk/role checks, approval handling and masking are used across ad-hoc,
workspace and preview execution. Redis supports shared login throttling and
execution cancellation signalling. Slack is an optional approval adapter.

## Retained decisions

| Boundary | Implementation and rationale | Original IDs |
| --- | --- | --- |
| Metadata schema | Alembic owns schema; startup verifies indexes/constraints rather than trusting revision stamping or `create_all()` | ADR-0001, 0015 |
| Startup configuration | Missing signing/encryption/database/Redis settings fail startup; production requires secure cookies | ADR-0004 |
| Target privileges | DBA provisions `ro`, `rw`, optional `ddl` accounts; WebQuery stores encrypted credentials, not a server-wide privileged login | ADR-0005 |
| Pool lifecycle | UUID/tier key, TTL cleanup, bounded pools: `ro` 10/20, `rw` 5/10, `ddl` 1/2 (size/overflow) | ADR-0003 |
| Sessions | Short JWT access token plus hashed opaque rotating refresh token and persisted session state; logout/disable checked server-side | ADR-0008, 0012 |
| Registration | Exact allowed email domains; empty list disables self-registration; activation required by default | ADR-0013 |
| Login protection | Redis required independently of worker count; outages fail login closed before password verification | ADR-0014 |
| Approval concurrency | Conditional pending-to-final update in a transaction; shared in-app and Slack decision service prevents double decisions | ADR-0011, 0019 |
| Platform governance | Persisted OWNER, trusted CLI bootstrap, at least one active OWNER; OWNER is not implicit target-query access | ADR-0017 |
| Target lifecycle | Soft deletion retains audit/workspaces; re-register reactivates; rename propagates saved target names atomically | ADR-0021 |
| SQL risk boundary | Analyzer is a policy signal, not a SQL sandbox; ADMIN retains documented bypass of non-hard-block risks | ADR-0016 |
| Masking | Match rules against query tables, support `full` only, return actual `masked_columns`; ADMIN deliberately bypasses | ADR-0018 |
| Audit/errors | Common audit writer and naive UTC timestamps; sanitize target errors and redact passwords; structured trace propagation | ADR-0006, 0009 |
| Frontend | Shared tokens/primitives, React + TypeScript, CodeMirror editor; design contract in `frontend/DESIGN.md` | ADR-0010 |
| Export | `write-excel-file` replaces the old XLSX dependency; CSV/XLSX export only displayed results | ADR-0024 |
| CI | Blocking correctness lint, tests, dependency audits and frontend checks; full style lint informational; real MSSQL job | ADR-0002, 0025 |

## Compatibility and accepted boundaries

New registrations accept only `ro`, `ro_rw`, `ro_rw_ddl`; higher tiers cannot
exist without lower ones. Roles are stored in `UserDatabaseAssociation.role`.
The derived `is_admin` column still exists, but authorization reads the role.
Database ADMIN manages a registration and can execute up to its provisioned
tier; platform OWNER alone does not grant database ADMIN or a query tier.

Legacy registrations without any tier credentials still fall back to
`CENTRAL_DB_USER/CENTRAL_DB_PASSWORD` for `ro`/`rw`. This is compatibility, not
the desired final least-privilege model. Removal needs a migration plan.

Metadata/bootstrap migrations use a metadata-database owner account. The
bundled SQL Server bootstrap also uses `sa` and assumes its password equals the
application-login password. Do not describe this as privileged credentials
being entirely absent; the future bootstrap separation is in the implementation
plan. Target tier accounts must remain separate from metadata credentials.

`EncryptedText` uses Fernet/MultiFernet for saved SQL and target passwords.
Decrypt failures currently log an error and return the original stored value
for legacy plaintext compatibility. This is not fail-closed decryption; key
rotation requires retaining old keys until all affected rows are rewritten.

## Cancellation: implemented, with outstanding policy differences

The implementation follows the recorded behavior in SPEC-0032. Body
`execution_id` is optional for old clients; the current UI always supplies one.
Redis TTL state is keyed by authenticated user and UUID. MSSQL uses cursor
SQLCancel; PostgreSQL/MySQL use a control connection with the selected tier
account. Commit is sealed atomically against cancellation, and the watcher is
drained before the connection returns to its pool. Cancelling the browser
request alone is not considered target cancellation.

ADR-0027 is **Proposed**, an implementation record, not an accepted replacement
for ADR-0026 (also Proposed). Earlier OQ-2026-021 required all new executions to
fail closed on registry failure and retain local cancellation of active work
during a Redis outage. The implementation does not fully meet that decision:
ID-less requests bypass the registry and cancel requests require Redis.
The older header/state-GET/PubSub design is **not implemented**. These differences
remain explicit work, not a changed user decision.

## Deployment limits

The base Compose removes source bind mounts and host database ports and runs the
API non-root. It still uses HTTP port 80, mutable image tags, a broad default
trusted-proxy CIDR and a SQL Server bootstrap password assumption. It is a
deployment starting point, not proof of a production-ready SaaS or tenant
isolation. TLS termination, restricted ingress, backups/key recovery and restore
tests are operator responsibilities. No billing, shared-tenant model, SLA or
customer deployment automation is implemented.

Accepted source-worktree decisions ADR-0022 and ADR-0023 retain two future
directions: remove the stored admin mirror while deriving API state from `role`,
and deploy isolated stacks per customer inside their VPN, not a shared-tenant
metadata system. They were uncommitted in the source checkout and are recorded
as pending implementation in this baseline, not silently applied migrations or
an approved new deployment.
