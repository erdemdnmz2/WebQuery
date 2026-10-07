# Implemented feature contracts

This is the consolidated current behavior reference. Listed tests are evidence
locations, not a claim that live services or GitHub CI ran in this session.
Security-sensitive changes require a new/updated spec before implementation.

| Feature | Source | Existing regression evidence (under `web_api/tests/`) |
| --- | --- | --- |
| Startup validation, encryption/rotation | `common/config_guard.py`, `app_database/models.py` | `unit/test_config_guard.py`, `unit/test_encrypted_text.py` |
| Access/refresh sessions and account disable | `authentication/`, `middlewares/auth_middleware.py` | `integration/test_auth_api.py`, `integration/test_user_lifecycle.py` |
| Domain allowlist, activation, login throttling | `authentication/config.py`, `login_throttle.py` | `integration/test_domain_registration_activation.py`, `integration/test_login_throttle_api.py`, `unit/test_login_throttle.py` |
| OWNER and scoped ADMIN governance | `owner/`, `admin/`, `common/roles.py` | `integration/test_owner_governance.py`, `test_admin_auth.py`, `test_access_management.py`, `unit/test_roles.py` |
| Tier credentials, UUID lookup, engine cache | `database_provider/`, `app_database/app_database.py` | `unit/test_database_provider_uuid.py`, `test_database_config.py`, `test_engine_cache.py`, `integration/test_database_capability.py` |
| Target soft delete/update/reactivation | `owner/services.py`, `owner/schemas.py` | `integration/test_database_lifecycle.py` |
| SQL analysis, bounded reads, transactions | `query_execution/query_analyzer.py`, `runner.py`, `services.py`, `database_provider/database.py` | `unit/test_query_analyzer.py`, `test_query_runner.py`, `integration/test_query_execution.py`, `test_target_transaction.py` |
| Saved workspaces and approval races | `workspaces/`, `approval/service.py` | `integration/test_workspaces.py`, `test_advanced_security.py` |
| Table-aware full masking | `common/security.py`, `query_execution/services.py`, `workspaces/services.py` | `unit/test_table_aware_masking.py`, `test_masked_columns.py`, `test_masking_rule_audit.py` |
| Audit, error sanitization, trace, trusted proxy | `common/audit*`, `errors.py`, `logging_config.py`, `middlewares/` | `unit/test_audit_log.py`, `test_error_scrubbing.py`, `test_logging_hardening.py`, `test_trusted_proxy.py`, `integration/test_error_handling_and_trace.py` |
| Optional Slack approvals | `slack_integration/`, `notification/`, `approval/service.py` | `integration/test_notifications_and_slack.py`, `unit/test_slack_approval_payload.py` |
| Driver-level cancellation | `query_execution/cancellation.py`, `frontend/lib/query-cancellation.ts`, `components/app/QueryCancelControl.tsx` | `unit/test_query_cancellation.py`, `integration/test_query_cancellation_api.py`, `mssql/test_target_cancellation.py` |
| Metadata schema and migrations | `migrations/`, `common/schema_contract.py`, `schema_guard.py` | `unit/test_baseline_migration.py`, `test_schema_contract.py`, `test_schema_guard.py`, `mssql/test_mssql_migration.py` |
| React UI and export | `frontend/pages/`, `components/`, `lib/export.ts`, `services/api.ts` | Frontend typecheck, API/contrast audits, XLSX verification and build; **no frontend behavioral test command on this baseline** |

## Authentication and governance

- F-01: Authentication tokens use HttpOnly, SameSite=Strict cookies; production
  requires Secure. Refresh cookie is scoped to `/api/refresh`. Session state and
  account activation are checked server-side; raw refresh tokens are not stored.
- F-02: Empty `ALLOWED_EMAIL_DOMAINS` disables self-registration. Exact domains
  are normalized; new users require activation unless explicitly configured off.
- F-03: Redis login throttle is account/IP scoped and fails closed on outage.
  SlowAPI limits remain an additional process-level mechanism, not a complete
  distributed limit for every API endpoint.
- F-04: First OWNER is created/promoted through the server-side CLI, never an
  HTTP self-escalation route. Last-active-owner and self-management safeguards
  apply. OWNER must grant target access separately.

## Target registration and access

- F-05: Provision `ro`, `ro+rw` or `ro+rw+ddl` credentials in the target DB first;
  WebQuery does not create/grant target accounts. Stored passwords use
  `EncryptedText`; listing endpoints do not return credential values. Users see
  an effective capability (registration mode intersected with role), not secrets.
- F-06: Removing a target marks it inactive and retains related data. Re-adding
  an inactive server/database pair reactivates it. PATCH omits unchanged fields.
  Renames update saved-query target-name pairs in the same transaction. Mode
  narrowing with incompatible grants returns `409`; fix those grants first.
- F-07: Query/workspace targets use UUID strings. Some administrative resources
  still expose integer IDs; this is not an all-UUID API. UUID indexing alone does
  not establish UUID uniqueness on every model.

## Query and approval behavior

- F-08: SQL is parsed into a shared plan for role/tier, risk and table analysis.
  `sql_injection_risk` and `blocked_operation` are hard blocks even for ADMIN.
  ADMIN's bypass of other risks is retained and logged/audited. Performance risk
  defaults to a warning. There is no universal destructive-DML confirmation.
- F-09: Pure reads stream and fetch limit+1 to distinguish exact-limit results
  from truncation. Response rows are capped. Mixed/unclassified/write-result
  paths remain buffered; this is not a memory bound for every possible batch.
- F-10: Successful target writes commit; failed/cancelled work rolls back before
  connection reuse. DB automatic commits or explicit COMMIT inside user SQL
  cannot be retroactively rolled back by the API.
- F-11: A pending approval can be decided once; repeat/concurrent decisions
  conflict rather than silently overwriting. In-app and Slack routes share the
  decision service. Slack approval messages carry the query UUID and require a
  matching authorized active WebQuery identity.
- F-12: `POST /api/multiple_query` is removed. A SQL text batch is not the old
  endpoint: only the exposed result set is returned; complete multi-result and
  per-statement affected-count reporting are not implemented.

## Masking, audit and cancellation

- F-13: Only `full` masking is supported. Rules match the query's referenced
  tables and then result column names; legacy blank-table rules apply broadly.
  ADMIN bypasses masking. UI uses response `masked_columns`, not requested rules,
  for its indicators. This is **not complete column lineage**: aliases and joins
  can defeat precision or cause over-masking. Enforce sensitive access with
  target DB grants/views; do not treat result masking as a complete security
  boundary for arbitrary SQL.
- F-14: Target-error responses are sanitized; stored diagnostic errors redact
  password patterns. Common audit records, UTC writes and trace IDs remain.
  Sanitization is not a guarantee against every sensitive value appearing in
  SQL/logs; API-wide non-query error hardening remains outside the original scope.
- F-15: Execute requests optionally carry a UUID in `execution_id`; current UI
  sends one on each run. `POST /api/query_executions/{execution_id}/cancel`
  returns `202 {"status":"cancelling"}` for acceptance, not completion.
  Unknown/another user's ID returns `404`; sealed/completed work `409`; registry
  outage `503`. The original request returns `409 QUERY_CANCELLED` once target
  execution and cleanup finish. UI stays busy until that original response.
- F-16: Redis failure blocks execution **when an execution ID is present**.
  Legacy ID-less requests retain compatibility and skip registration. Cancel is
  Redis-dependent. Earlier all-execution/local-outage policy is not fully met;
  see [implementation plan](implementation-plan.md), P1.

## Validation boundary

Normal backend tests use in-memory SQLite and service doubles. Real MSSQL
schema/auth/governance/query/cancellation coverage is a separate CI job using
an explicitly disposable `webquery_ci` database and Redis. Real PostgreSQL/MySQL
cancellation, staging restore/upgrade and frontend behavioral coverage are still
gaps. A mock passing does not establish live-driver behavior.
