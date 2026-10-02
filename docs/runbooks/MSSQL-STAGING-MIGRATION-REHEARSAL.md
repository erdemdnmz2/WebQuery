# MSSQL staging migration rehearsal

This runbook is for an authorized, non-production copy of one customer's
metadata database. It is not a CI procedure and must never use a production
backup or credential in a pull request runner.

## Preconditions

- A current backup has been restored into an isolated staging SQL Server.
- The operator has written authorization for the restore, migration and smoke
  test window.
- The staging application uses its own `SECRET_KEY`, Fernet key and database
  credentials; no customer secret is copied into source control or CI logs.
- Before applying the masking-rule migration, check for duplicate rules:

```sql
SELECT database_id, table_name, column_name, COUNT(*) AS duplicate_count
FROM MaskingRules
GROUP BY database_id, table_name, column_name
HAVING COUNT(*) > 1;
```

Resolve every returned duplicate before proceeding.

## Procedure

1. Record the source backup identity, restore timestamp, target server and
   authorized operator in the change ticket; do not record credentials.
2. Restore the backup into the isolated staging instance and confirm the
   application database is reachable with the staging runtime account.
3. Set the staging `APP_DATABASE_URL` and run:

   ```bash
   cd web_api
   python -m alembic upgrade head
   ```

4. Record elapsed time and any SQL Server lock waits from the staging
   monitoring console.
5. Start the application. Its startup schema guard must succeed.
6. Smoke-test login, a least-privilege user, OWNER/DB ADMIN operations, audit
   log creation, target-database registration and one permitted query write.
7. Re-run `alembic upgrade head` to prove idempotence, then document the
   rollback decision. Schema migrations are not automatically reversible; a
   rollback is restore-from-backup unless the specific revision has an approved
   downgrade plan.

## Evidence to retain

- Alembic command exit status and elapsed time.
- Schema guard success.
- Smoke-test identifiers and audit-log references, with credentials redacted.
- Restore point and approval/change-ticket reference.
