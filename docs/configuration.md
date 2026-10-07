# Configuration

The backend template is [`.env.example`](../.env.example) at repository root.
Copy it to `.env`, supply secrets privately, then choose your runtime profile.
Do not create a second backend template or copy real values into documentation.

## Loading and profiles

`app.py` loads `ENV_FILE` before domain imports; default is `.env`. The example
uses `../.env` for native startup from `web_api/`. Domain modules and CLIs also
use python-dotenv discovery, which can find the root file. The metadata config
loads `web_api/.env.production` first when present; existing process variables
win over dotenv. Avoid several competing files; prefer explicit process
variables for a deployment. Compose injects root `.env` with `env_file`; it
overrides metadata URL, DB host and Redis address inside containers.

| Profile | Required settings |
| --- | --- |
| Native/local HTTP | Fill required secrets/metadata URL; `DEBUG=true`, `COOKIE_SECURE=false`; frontend proxy on port 3000 |
| Production/HTTPS | `DEBUG=false`, `COOKIE_SECURE=true`; exact app origin, trusted proxy ranges, TLS termination and access restrictions |
| Bundled Compose | Set `DB_USER`, `DB_PASSWORD`; database name is hardcoded to `dba_application_db`; URL/Redis overrides described below |

The committed example favors production cookie settings and intentionally has
blank secrets. It is not a ready-to-deploy production configuration.

## Required secrets and metadata settings

| Variable | Default / requirement | Source / meaning |
| --- | --- | --- |
| `SECRET_KEY` | Required; >=32 characters | `common/config_guard.py`; JWT signing key |
| `QUERY_ENCRYPTION_KEY` | Required unless plural supplied | Valid Fernet key for stored SQL/password fields |
| `QUERY_ENCRYPTION_KEYS` | Optional ordered CSV | Overrides singular; first key writes, all keys decrypt; `app_database/models.py` |
| `APP_DATABASE_URL` | Explicit value required at app startup | Full async SQLAlchemy metadata URL; metadata config has a builder fallback only for other callers |
| `DB_USER`, `DB_PASSWORD` | Empty in code | Builder/bootstrap components; Compose requires both; not user-query target credentials |
| `DB_HOST` | `localhost` | Metadata builder host; Compose sets `db` |
| `DB_NAME` | `dba_application_db` | Metadata builder database; Compose URL uses the literal name, not this variable |
| `CENTRAL_DB_USER`, `CENTRAL_DB_PASSWORD` | Explicit values required by guard | Legacy no-tier target registrations still use these for `ro`/`rw`; provider alone falls back to DB_USER/DB_PASSWORD |
| `SQL_SERVER_NAMES` | `localhost` | Legacy comma-separated catalogue constant; it does not register new targets |
| `REDIS_URL` | Required by guard and login throttle | Native example `redis://localhost:6379/0`; Compose sets `redis://redis:6379/0` |

Generate signing and Fernet keys **on your own machine**, save the output in your
secret store and do not post it to an issue/chat:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Fernet is not an arbitrary string. Losing old keys makes encrypted rows
unrecoverable. Rotation does not rewrite existing rows automatically: retain
the old keys, rewrite/verify all encrypted fields, then remove retired keys.
Restart processes after key-list changes because `EncryptedText` caches the
keyring. Decrypt failures currently log and return raw stored text rather than
rejecting it; see the hardening plan.

Native MSSQL URLs must URL-encode credential components. The bundled Compose
URL uses raw `${DB_USER}:${DB_PASSWORD}` interpolation, unlike the target URL
builder; reserved URL characters can break it. This packaging pass does not
silently change that connection contract. Bootstrap assumes the same password
for `sa` and the metadata application login; isolate this development setup and
do not present it as a final production-secret separation design.

## Authentication and rate limits

Source: `authentication/config.py`, `sessions.py`, `login_throttle.py`.

| Variable | Code default | Notes |
| --- | --- | --- |
| `ALLOWED_EMAIL_DOMAINS` | Empty | Exact CSV domains; empty disables self-registration; leading `@` accepted |
| `REGISTRATION_REQUIRES_ACTIVATION` | `true` | OWNER activates new users |
| `JWT_ALGORITHM` | `HS256` | Keep compatible with the signing-key design |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `20` | Access-token lifetime |
| `REFRESH_TOKEN_EXPIRE_HOURS` | `12` | Refresh-token lifetime |
| `REFRESH_GRACE_SECONDS` | `30` | Concurrent refresh grace window |
| `SESSION_TIMEOUT_MINUTES` | `60` | Legacy config constant; not the current persisted refresh TTL |
| `RATE_LIMITER` | `3/minute` | Login SlowAPI rate expression |
| `REFRESH_RATE_LIMITER` | `30/minute` | Refresh SlowAPI rate expression |
| `LOGIN_MAX_FAILURES` | `5` | Positive integer; Redis account/IP failure threshold |
| `LOGIN_WINDOW_MINUTES` | `15` | Positive integer; Redis sliding window |
| `LOGIN_THROTTLE_KEY_PREFIX` | `webquery:login-throttle` | Non-empty Redis key namespace; cancellation uses its own fixed prefix |
| `COOKIE_SECURE` | `False` | Must be `true` when DEBUG=false; all boolean settings use `true`/`false` strings |
| `CORS_ALLOWED_ORIGINS` | `*` | Code default is broad; example narrows it. Same-origin dev proxy avoids credentialed CORS |
| `TRUSTED_PROXY_IPS` | Empty | Comma-separated IP/CIDR ranges, never `*`; trust only actual peers |

Login throttle fails closed on Redis outage. Current execution registration
also fails closed for ID-bearing requests; ID-less compatibility requests skip
it. SlowAPI per-process limits are not a global distributed API limit.

## Queries and pools

Source: `query_execution/config.py`, `database_provider/config.py`.

| Variable | Code default | Notes |
| --- | --- | --- |
| `QUERY_TIMEOUT_SECONDS` | `300` | Target statement budget; not pool acquisition or login timeout |
| `MAX_ROW_COUNT_LIMIT` | `1000` | Maximum returned rows; read path fetches one extra for truncation |
| `MAX_ROW_COUNT_WARNING` | `10000` | Row-count warning threshold; capped read counts may never reach it |
| `QUERY_RATE_LIMITER` | `10/minute` | Execution/cancel SlowAPI limit |
| `MAX_JOINS` | `8` | Performance-risk threshold |
| `PERFORMANCE_BLOCKS` | `false` | Performance findings warn by default |
| `ENGINE_CACHE_TTL_SECONDS` | `1800` | Idle cached-engine lifetime/cleanup interval |

MSSQL login timeout is fixed at 30 seconds and its query timeout is applied to
the driver connection. PostgreSQL uses statement/command timeouts. MySQL uses
`max_execution_time` for read-only SELECT; it does not bound DML in the same
way. Tune positive limits conservatively; not every numeric setting is guarded
against an invalid/negative value at startup.

## Optional integrations and process settings

| Variable | Code default | Notes |
| --- | --- | --- |
| `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_ADMIN_CHANNEL` | Unset | Supply together for Socket Mode approvals; blank leaves integration unavailable without failing API startup |
| `SLACK_URL` | Unset | Optional legacy webhook notifications; URL is a secret |
| `ENV_FILE` | `.env` | app.py initial dotenv file; see loading section |
| `DEBUG` | `false` | `true` enables reload; development only |
| `LOG_LEVEL` | `INFO` | Central logging setup |
| `HOST` | `0.0.0.0` | API listen address |
| `PORT` | `8080` | API port; keep aligned with nginx upstream |
| `WORKERS` | `1` | Uvicorn workers; reload and workers do not combine |
| `VITE_API_TARGET` | `http://localhost:8080` | Frontend dev proxy; optional `frontend/.env.example`, never a credential |

Test-only `MSSQL_CI`, `MSSQL_TEST_URL` and workflow-only `CI_FERNET_KEY` are not
production settings and do not belong in your application `.env`. MSSQL tests
can reset a database: use only the disposable `webquery_ci` target.

## Compose differences and verification

The base defaults `TRUSTED_PROXY_IPS` to `172.16.0.0/12` even if the example is
blank; the development override explicitly clears it. A CIDR is not proof that
only nginx is trusted. Match the actual network and test forwarded-header
handling. Base Compose exposes HTTP 80, not HTTPS. Configure TLS before using
the production cookie profile. Neither Git ignores nor Docker ignores revoke
already leaked credentials or replace a secret scanner.

Use `make prod-config` / `make dev-config` for quiet syntax validation. Do not
share raw `docker compose config` output: it expands secret values.
