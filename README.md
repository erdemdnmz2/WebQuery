# WebQuery - Enterprise SQL Execution Platform

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Architecture](https://img.shields.io/badge/architecture-modular-orange)

WebQuery is a secure enterprise SQL execution platform built on FastAPI. It allows teams to safely run, share, and audit queries across multiple target databases (MSSQL, MySQL, PostgreSQL).

Access to a target database is granted **per database, per privilege tier**: the
target database's own DBA creates least-privilege accounts on the target server,
an administrator registers them in WebQuery, and WebQuery connects with the
account that matches the tier the query actually needs. Around that sit AST-based
query analysis, server-side sessions, an append-only audit log, and request
tracing.

> [!IMPORTANT]
> Architecture decisions live in `docs/adr/` and feature contracts in
> `docs/specs/`. Where this README and an ADR disagree, the ADR is correct — see
> `AGENTS.md` for the working agreement.

---

## Architecture & Core Features

### 1. Role-Based Target Database Credentials
* **UUID-Based Abstraction:** Access to target databases uses unique UUID identifiers instead of exposing raw server or database names in the endpoints.
* **Per-database, per-tier accounts (ADR-0005):** Each registration stores up to three target-database accounts — `ro` (read-only), `rw` (read/write) and `ddl`. WebQuery never creates these accounts and holds no `CREATE LOGIN`/`GRANT` rights on the target server; the target DBA creates them and an administrator enters them. A registration is one of three connection modes: `ro`, `ro + rw`, or `ro + rw + ddl`. `rw` and `ddl` cannot exist without the tiers below them.
* **WebQuery Roles:** `READER`, `WRITER`, `DDL` and `ADMIN` are enforced per user per database via `UserDatabaseAssociation`. A separate, platform-wide `OWNER` role governs user activation, target database registration and DB ADMIN assignment (ADR-0017). `OWNER` grants no query-execution rights of its own.
* **Effective Privilege:** What a user may run is the intersection of the registration's connection mode and their role — a `READER` on a `ro + rw` database gets `ro`. The SQL editor shows that effective privilege, not the registration's mode, so the UI never promises a capability execution would refuse.
* **Credential Encryption at Rest:** Stored target-database passwords and saved query text are encrypted with **Fernet** (AES-128-CBC + HMAC-SHA256) via an ORM type decorator. `QUERY_ENCRYPTION_KEYS` holds a comma-separated list, newest first, which is what makes key rotation possible.
* **Dynamic Data Masking:** Masking rules redact sensitive columns for non-admin roles during execution. Enforcement is **table-aware** (ADR-0018): a rule on `Customers.email` does not mask `Suppliers.email`.
* **Granular Audit Logging:** `ActionLogging` records query executions; the append-only `AuditLog` table records non-execution security events (access grants, role changes, database registration, password changes, session revocation) with actor, trace ID and client IP.
* **Server-Side Sessions (ADR-0008):** A short-lived access token in an HttpOnly cookie plus a rotating refresh token backed by a server-side `UserSessions` row. Sessions are revocable; refresh-token reuse revokes every active session for that user.
* **Login Throttling:** Per-user and per-IP login throttling backed by **Redis**, which is a hard runtime dependency, not an optimisation. If Redis is unreachable, `/api/login` fails closed with `503` rather than falling back to unthrottled bcrypt verification (ADR-0014).

### 2. Connection Pooling & Engine Cache
* **Per-tier pools (ADR-0005):** Each target database keeps a separate engine per privilege tier, sized to expected use: `ro` 10/20, `rw` 5/10, `ddl` 1/2 (`pool_size`/`max_overflow`).
* **Stale-connection handling:** Both the target engines and the application metadata engine use `pool_pre_ping=True`, so a connection dropped by a restart or a firewall is replaced transparently instead of failing the request.
* **LRU Eviction & TTL Cleanup:** Least Recently Used engines are evicted when the cache limit is reached, and a background task disposes engines idle beyond `ENGINE_CACHE_TTL_SECONDS` (default 1800). An engine with checked-out connections is never disposed; if every pool is busy, the cache raises rather than pulling a connection out from under a running query.

### 3. Dynamic SQL Risk Analysis (AST Parsing)
Before execution, every query is parsed once by `QueryAnalyzer` using `sqlglot`, with the target's dialect (`tsql`, `mysql`, `postgres`). The resulting plan feeds the role check, the tier decision and the risk assessment. Risk levels:

1. **SQL Injection (`sql_injection_risk`):** Not a pattern match on the query text. The parse itself is the check — a query sqlglot cannot parse is blocked outright — plus dynamic execution and privilege escalation inside an opaque `exp.Command` (`EXEC`, `EXECUTE AS`, `XP_CMDSHELL`).
2. **Blocked Operation (`blocked_operation`):** OS, filesystem and remote-SQL functions (`xp_cmdshell`, `openrowset`, `pg_read_file`, `lo_import`, …), over-long sleeps, and `EXPLAIN ANALYZE` — which really executes the statement it wraps.
3. **DDL (`ddl_pattern`):** `DROP`, `CREATE`, `ALTER`, `TRUNCATE`.
4. **Risky DML (`risky_pattern`):** `DELETE` or `UPDATE` without a `WHERE` clause.
5. **Performance (`performance_risk`):** More than `MAX_JOINS` (default **8**) joins, `CROSS JOIN`s, leading-wildcard `LIKE`, or very large row requests. Advisory by default; set `PERFORMANCE_BLOCKS=true` to make it blocking.

`sql_injection_risk` and `blocked_operation` are **hard blocks**: no role, including a database ADMIN, can execute past them. The other three are judgement calls a database ADMIN may take responsibility for, and every such bypass is logged and audited (ADR-0016).

> [!NOTE]
> **Approval Workflow:** Risky queries submitted by non-admin users are automatically put into a "Pending Approval" state. Authorized administrators can inspect, approve, or reject these queries via Slack or the Admin Panel. The Slack notification carries the query text — a deliberate decision recorded in ADR-0019, along with the resulting requirement that the approval channel be access-controlled.

### 4. Advanced Request Tracing & Auditing Middleware
* **Trace ID Generation:** The `TraceMiddleware` automatically assigns a unique UUID (Trace ID) to every incoming HTTP request and attaches it as the `X-Request-ID` header in the response.
* **Context-Aware Auditing:** Utilizes Python `contextvars` to dynamically propagate the active Trace ID and authenticated User ID to all logging handlers. Every log entry automatically prints the trace context without passing request objects down the call stack.

### 5. Unified Error Translation (Exception Translation Pattern)
* **Modular Domain Exceptions:** Low-level infrastructure, driver, or database errors (such as SQLAlchemy or network exceptions) are caught at the service boundary and translated into domain-specific exceptions (e.g., `WorkspaceNotFoundError`, `QueryExecutionError`, `UserAlreadyExistsError`).
* **Global Handling:** A centralized exception handler intercepts all domain exceptions, logs their detailed tracebacks internally, and returns a clean, secure, and standardized JSON response containing `success: false`, the enterprise `error_code`, a safe client-facing `message`, and the associated `trace_id`.

### 6. Centralized Dependency Injection Container (AppContext)
* **Application Lifespan Scope:** Core stateless services (`QueryService`, `WorkspaceService`, `AdminService`, and `NotificationService`) are instantiated inside a unified `AppContext` container during application startup.
* **Reduced Re-instantiation Overhead:** Re-creation of service classes on every HTTP request is eliminated, optimizing server performance and ensuring thread-safe, application-scoped instance reuse.
* **Full Autocomplete & Type Safety:** Placing the structured `AppContext` on `app.state.context` provides full IDE autocomplete support and static analysis validation.

---

## Directory Structure

WebQuery adopts a clean, modular package architecture:

```
web_api/
│
├── common/                  # Centralized utilities
│   ├── exceptions.py        # BaseServiceException and global hierarchy
│   ├── roles.py             # The one place role strings are parsed
│   ├── clock.py             # db_now(): the one clock for app-DB timestamps
│   ├── audit.py             # Transaction-aware AuditLog writers
│   ├── config_guard.py      # Fail-closed startup configuration checks
│   ├── schema_guard.py      # Startup schema-integrity verification
│   ├── security.py          # Masking rule resolution
│   ├── logging_config.py    # Custom contextvars logger formatting
│   └── limiter.py           # Consolidated, shared slowapi Limiter
│
├── middlewares/             # FastAPI Middlewares
│   ├── proxy_middleware.py  # Real client IP from X-Forwarded-For, trusted peers only
│   ├── trace_middleware.py  # Request ID generation and log context binding
│   └── auth_middleware.py   # Session validation and user context binding
│
├── database_provider/       # Connection management and target DB sessions
│   ├── database.py          # DatabaseProvider session generator
│   ├── engine_cache.py      # Per-tier, LRU and TTL-based engine caching
│   └── config.py            # Target database driver and timeout configuration
│
├── query_execution/         # SQL execution and AST risk analysis
│   ├── query_analyzer.py    # QueryPlan: one parse feeds role, tier and risk
│   ├── runner.py            # Shared execution path (streaming for pure reads)
│   ├── services.py          # QueryService with SELECT and DML execution safety
│   └── router.py            # Query execution HTTP entrypoints
│
├── app_database/            # Application (metadata) database models and access
├── authentication/          # Registration, login, sessions, refresh rotation
├── approval/                # In-app approval decisions for pending queries
├── workspaces/              # User workspace management (saved queries)
├── admin/                   # Database-scoped administration (access, masking, approvals)
├── owner/                   # Platform OWNER governance + first-OWNER bootstrap
├── slack_integration/       # Socket-mode approval bot
├── notification/            # Slack webhook notifications
├── migrations/              # Alembic revisions (ADR-0001)
├── scripts/                 # Server-side CLIs (bootstrap_owner.py)
└── tests/                   # Unit and integration tests (SQLite in-memory)
```

---

## Driver Requirements

To connect to target databases, the corresponding system-level drivers and client libraries must be installed on your host machine:

### **Microsoft SQL Server (MSSQL)**
* **ODBC Driver 18 for SQL Server** (System-level installation is mandatory).
  * Windows: [Microsoft ODBC Download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
  * Linux/macOS: [ODBC Installation Guide](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
  * Python packages: `aioodbc`, `pyodbc` (included in requirements)

### **MySQL**
* Python packages: `aiomysql`, `PyMySQL` (included in requirements)

### **PostgreSQL**
* Python package: `asyncpg` (included in requirements)

---

## Quick Start (Development)

### 1. Clone the Repository
```bash
git clone https://github.com/erdemdnmz2/WebQuery
cd WebQuery
```

### 2. Set Up Virtual Environment and Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r web_api/requirements.txt
```

### 3. Configure Environment Variables
Copy the template `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```

Startup is **fail-closed**: `common/config_guard.py` refuses to start the
application when a required value is missing or left at its placeholder
(ADR-0004). The required set is:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Session token signature. Minimum 32 characters. `openssl rand -hex 32` |
| `APP_DATABASE_URL` | WebQuery's own metadata database |
| `CENTRAL_DB_USER` / `CENTRAL_DB_PASSWORD` | Legacy central account, still required by the guard. Runtime query connections use the per-database, per-tier accounts from ADR-0005 |
| `REDIS_URL` | Login throttle backing store. A hard dependency — see ADR-0014 |
| `QUERY_ENCRYPTION_KEY` or `QUERY_ENCRYPTION_KEYS` | Fernet key(s) for encryption at rest. **Not** the same format as `SECRET_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

With `DEBUG=false` the guard additionally requires `COOKIE_SECURE=true`.

> [!WARNING]
> Losing `QUERY_ENCRYPTION_KEY` makes every stored target-database password and
> saved query permanently unreadable. Keep it somewhere other than `.env` as
> well. Rotate by putting the new key first in `QUERY_ENCRYPTION_KEYS` and
> keeping the old one in the list until every row has been rewritten.

### 4. Start Redis
```bash
docker run -p 6379:6379 redis:7
```

### 5. Initialize Database
Create the metadata database and apply migrations:
```bash
cd web_api
python create_db.py
alembic upgrade head
```

### 6. Create the First Platform OWNER
The first `OWNER` cannot be granted over HTTP; it is a server-side action
(ADR-0017). From `web_api/`:
```bash
python -m scripts.bootstrap_owner --email owner@example.com --username owner
```
Omit `--username` to promote a user who already exists. The OWNER then activates
users, registers target databases and assigns database ADMINs from the app.

### 7. Run the Application
Start the Uvicorn development server:
```bash
python app.py
```
The API will be accessible at `http://localhost:8080` with interactive Swagger docs at `http://localhost:8080/docs`.

### Docker
`docker-compose.yml` is the **production-safe** base: no source bind mount, no
published database port, and a non-root application user. It is also what the
bare command resolves to, so a deploy cannot get the development topology by
forgetting a flag.

`docker-compose.dev.yml` holds the development conveniences — a `./web_api`
bind mount for live reload, plus `8080` and `1433` published to the host — and
must be requested explicitly. The `Makefile` keeps that short:

```bash
docker compose up   # production-safe topology (the default)
make up             # development: base + docker-compose.dev.yml
make prod-config    # print what a deploy will actually run, before deploying
```

Before deploying, `make prod-config` should show exactly one published port
(`80`, nginx) and no bind mount other than `nginx.conf`.

Behind a reverse proxy, set `TRUSTED_PROXY_IPS` to the proxy's address range.
Client IPs are taken from `X-Forwarded-For` only when the immediate peer is in
that list; otherwise every request would appear to come from the proxy and
per-IP throttling would apply to the whole platform as one bucket.

---

## Frontend Setup (Development)

The WebQuery frontend is a modern React application built with Vite, TypeScript, and Tailwind CSS.

### 1. Navigate to the Frontend Directory
```bash
cd frontend
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Run the Development Server
```bash
npm run dev
```
The application will be accessible at `http://localhost:5173` (or the port specified by Vite) and will automatically proxy API requests to the backend server running at `http://localhost:8080`.

---

## Testing

The backend test suite runs entirely in memory against SQLite
(`sqlite+aiosqlite:///:memory:`), covering routes, middlewares, error
translation, authorization and SQL analysis without touching an external
resource.

```bash
cd web_api && pytest
```

Frontend checks (there is no frontend unit-test suite yet):
```bash
cd frontend
npm run typecheck      # tsc --noEmit
npm run build          # vite build
npm run audit:api      # every api.ts call matches a backend route
npm run audit:contrast # colour contrast targets
```

> [!NOTE]
> **Known testing gap.** Tests run against SQLite only. MSSQL-specific
> behaviour — `NVARCHAR`, `DATETIME2`, `UNIQUEIDENTIFIER`, statement timeouts
> and the absence of row-value `IN` — is not verified in CI. Migrations in
> particular are exercised against SQLite, not against a real SQL Server.

---

## Documentation Map

| Path | Contents |
| --- | --- |
| `AGENTS.md` | Working agreement for AI-assisted contributions (read first) |
| `docs/adr/` | Accepted architecture decisions — authoritative over this README |
| `docs/specs/` | Feature specifications and acceptance criteria |
| `docs/open-questions.md` | Project-wide decision queue |
| `docs/ai/playbooks/` | Reusable work procedures |
| `frontend/DESIGN.md` | Design tokens, component inventory, accessibility contract |

---

## License
This project is licensed under the MIT License.
