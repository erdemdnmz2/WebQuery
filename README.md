# WebQuery - Enterprise SQL Execution Platform

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Architecture](https://img.shields.io/badge/architecture-modular-orange)

WebQuery is a powerful, secure, and production-ready enterprise SQL execution platform built on FastAPI. It allows teams to safely run, share, and audit queries across multiple target databases (MSSQL, MySQL, PostgreSQL). 

Designed with zero-trust B2B security principles, WebQuery eliminates the need to store individual database credentials by employing a **Centralized Service Account Architecture** coupled with advanced AST-based query analysis, global error translation, and a real-time request tracing system.

---

## Architecture & Core Features

### 1. Centralized Service Account Architecture (Zero-Trust Security)
* **No User-Stored Credentials:** Individual database passwords are never requested, stored, or cached (removing any risk of credential leaks).
* **Central Credentials:** Connections to target databases are established dynamically using highly restricted central service credentials (`CENTRAL_DB_USER` and `CENTRAL_DB_PASSWORD`) defined securely in the environment.
* **Granular Audit Logging:** Although execution is centralized, every query is strictly audited. The platform logs the exact user, trace ID, timestamp, and machine name for every action in the `ActionLogging` table.
* **Stateless JWT Authorization:** Session management is completely stateless. Authenticated requests use cryptographically signed JWT tokens stored in secure, HttpOnly cookies, completely eliminating the need for a Redis credential cache.

### 2. Intelligent Connection Pooling & Engine Cache
* **Zero Idle Connections:** Connection engines to target databases are managed by an advanced `EngineCache`. It sets `pool_size=0` to release idle server-side connections immediately after query execution.
* **Max Overflow Handling:** Dynamically allows up to 20 concurrent connections during peak query bursts.
* **LRU Eviction & TTL Cleanup:** Least Recently Used (LRU) engines are evicted when the cache limit is reached. A background task cleans up expired engines based on a configurable Time-to-Live (TTL), while ensuring active, currently executing engines (`checkedout > 0`) are safely protected.

### 3. Dynamic SQL Risk Analysis (AST Parsing)
Before execution, every query is analyzed by a custom `QueryAnalyzer` utilizing the `sqlglot` library for abstract syntax tree (AST) parsing. It supports target-specific SQL dialects (`tsql`, `mysql`, `postgres`) and grades queries into four risk levels:
1. **SQL Injection:** Checks for structural anomalies (e.g., `UNION SELECT`, `OR 1=1`, inline comments).
2. **DDL (Structural Modifications):** Detects `DROP`, `CREATE`, `ALTER`, `TRUNCATE`.
3. **Risky DML:** Blocks `DELETE` or `UPDATE` statements lacking a `WHERE` clause.
4. **Performance Anomalies:** Flagging queries with more than 3 `JOIN`s, `CROSS JOIN`s, un-indexed `LIKE '%...%'`, or massive `LIMIT` operations.

> [!NOTE]
> **Approval Workflow:** Risky queries submitted by non-admin users are automatically put into a "Pending Approval" state. Authorized administrators can inspect, approve, or reject these queries via Slack or the Admin Panel.

### 4. Advanced Request Tracing & Auditing Middleware
* **Trace ID Generation:** The `TraceMiddleware` automatically assigns a unique UUID (Trace ID) to every incoming HTTP request and attaches it as the `X-Request-ID` header in the response.
* **Context-Aware Auditing:** Utilizes Python `contextvars` to dynamically propagate the active Trace ID and authenticated User ID to all logging handlers. Every log entry automatically prints the trace context without passing request objects down the call stack.

### 5. Unified Error Translation (Exception Translation Pattern)
* **Modular Domain Exceptions:** Low-level infrastructure, driver, or database errors (such as SQLAlchemy or network exceptions) are caught at the service boundary and translated into domain-specific exceptions (e.g., `WorkspaceNotFoundError`, `QueryExecutionError`, `UserAlreadyExistsError`).
* **Global Handling:** A centralized exception handler intercepts all domain exceptions, logs their detailed tracebacks internally, and returns a clean, secure, and standardized JSON response containing `success: false`, the enterprise `error_code`, a safe client-facing `message`, and the associated `trace_id`.

---

## Directory Structure

WebQuery adopts a clean, modular package architecture:

```
web_api/
│
├── common/                  # Centralized utilities (Exceptions, Logging, Rate Limiting)
│   ├── exceptions.py        # BaseServiceException and global hierarchy
│   ├── logging_config.py    # Custom contextvars logger formatting
│   └── limiter.py           # Consolidated, shared slowapi Limiter
│
├── middlewares/             # FastAPI Middlewares (Trace ID, Stateless Auth)
│   ├── trace_middleware.py  # Request ID generation and log context binding
│   └── auth_middleware.py   # JWT validation and user context binding
│
├── database_provider/       # Connection management and target DB sessions
│   ├── database.py          # DatabaseProvider session generator
│   ├── engine_cache.py      # LRU and TTL-based SQLAlchemy connection engine caching
│   └── config.py            # Central and target database driver configurations
│
├── query_execution/         # SQL execution, AST risk analysis, and audit logging
│   ├── services.py          # QueryService with SELECT and DML execution safety
│   └── router.py            # Query execution HTTP entrypoints
│
├── workspaces/              # User workspace management (Saved queries and metadata)
├── authentication/          # User registration, stateless login, and cookies
├── admin/                   # Administrative actions (Database registration, manual approvals)
└── tests/                   # Test Suite (Unit and Integration tests with SQLite in-memory)
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

Ensure the following variables are set correctly:
* `DB_USER` and `DB_PASSWORD` (For the WebQuery metadata application database)
* `CENTRAL_DB_USER` and `CENTRAL_DB_PASSWORD` (Central service account for target database executions)
* `SECRET_KEY` (Strong secret key for JWT signatures)
* `SQL_SERVER_NAMES` (Comma-separated list of target servers, e.g., `localhost`)

### 4. Initialize Database
Initialize the SQLite metadata database (or MSSQL if configured):
```bash
cd web_api
python create_db.py
```

### 5. Run the Application
Start the Uvicorn development server:
```bash
python app.py
```
The API will be accessible at `http://localhost:8080` with interactive Swagger docs at `http://localhost:8080/docs`.

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

WebQuery comes with a comprehensive testing suite that executes completely in memory using an SQLite async memory database (`sqlite+aiosqlite:///:memory:`) to verify routes, middlewares, error translation, and SQL execution without modifying any external resources.

Run the test suite using pytest:
```bash
pytest
```

---

## License
This project is licensed under the MIT License.
