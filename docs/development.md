# Development and validation

Use Python 3.11 and Node 24 to match the Dockerfiles and CI. SQL Server access
requires system ODBC Driver 18 in addition to the Python packages. The bundled
SQL Server container's platform support must be checked on your host; use a
compatible SQL Server host if it cannot run locally.

## First-time Docker development

1. Copy root `.env.example` to `.env`. Fill the required signing/Fernet and
   database credentials from [configuration](configuration.md). For **local
   HTTP only**, set `DEBUG=true`, `COOKIE_SECURE=false`. Leave secrets out of Git.
2. Set `DB_USER=webquery_app` and a strong `DB_PASSWORD` compatible with the
   current Compose URL interpolation. The bundled bootstrap shares this
   password between `sa` and the metadata login; it is a known limitation, not
   the production separation design. Target tier accounts are separate.
3. Build, start infrastructure and create the first OWNER before starting the
   API. These commands create a **new local** SQL Server database; do not point
   them at a customer server:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db redis
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -it web \
  python -m scripts.bootstrap_owner --email owner@example.com --username owner
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

The one-off web container runs the entrypoint: waits for SQL Server, creates the
metadata DB/login, applies Alembic, then executes the interactive OWNER CLI.
It prompts for the password without putting it in command history. Omit
`--username` to promote an existing user without changing their password.
App startup requires at least one active OWNER; an empty install cannot start
the API first and create its own OWNER through registration.

Open `http://localhost` for the container UI, or the development API at
`http://localhost:8080/docs`. OWNER registers target DBs and grants users roles.
Provision target DB tier accounts yourself before registering them.

Use `make logs`, `make ps` and `make down` for development. `down` without `-v`
retains database volumes; do not delete volumes or run destructive MSSQL tests
against valuable data. The dev override publishes 1433/8080 on host interfaces,
so use an isolated machine/firewall; it is not a production exposure policy.

## Native backend and frontend

Set up from repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r web_api/requirements.txt
cp .env.example .env
```

Configure `.env` privately. Native `APP_DATABASE_URL` must use an async driver
and properly URL-encoded credentials. Supply an existing local SQL Server and
Redis, or use only the Compose `db`/`redis` services (Redis has no host port in
the supplied Compose files; native API needs a separately reachable Redis).
`create_db.py` is specifically a SQL Server bootstrap, not a generic PostgreSQL
or MySQL setup tool. Skip it when your DBA has already provisioned metadata.

From `web_api/`, with the root virtual environment activated:

```bash
python create_db.py
alembic upgrade head
python -m scripts.bootstrap_owner --email owner@example.com --username owner
python app.py
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite listens on port **3000**, not 5173, and proxies `/api` to port 8080.
Use the frontend origin for login so same-origin cookies work. Optional
`frontend/.env.example` documents `VITE_API_TARGET`; no frontend secret is
required. A browser-facing `VITE_*` value must never hold credentials.

## Automated validation

The normal backend suite uses in-memory SQLite and dependency doubles. Ensure
test execution is isolated from deployment configuration, especially any
`MSSQL_TEST_URL`, before running:

```bash
cd web_api
env -u MSSQL_TEST_URL -u MSSQL_CI python -m pytest -q
ruff check --select F,E9 .
```

From `frontend/`:

```bash
npm ci
npm run typecheck
npm run verify:export
npm run verify:source-map-security
npm run audit:api
npm run audit:contrast
npm run build
npm audit --audit-level=high
```

These frontend checks are **not** behavioral unit/integration tests. There is
no `npm test` script on the imported baseline. Large editor-chunk warnings
must be reported but are not automatically build failures.

From repository root:

```bash
python3 scripts/check_repository.py
python3 -m unittest discover -s scripts/tests -v
make prod-config
make dev-config
```

Compose validation requires your local `.env`, does not start services, and
uses `--quiet` to avoid printing expanded secrets. The repository checker
reads only examples/source/docs; it never opens your real environment file.

## CI and real-service safety

`.github/workflows/ci.yml` runs backend, frontend and real MSSQL jobs on pushes
and PRs. Correctness lint and dependency audits block; broad style lint is
informational. The MSSQL job uses disposable SQL Server/Redis services and
validates migrations plus auth, governance, lifecycle, query and cancellation.

Real MSSQL tests require **both** `MSSQL_CI=1` and `MSSQL_TEST_URL` naming
`webquery_ci`; they may DROP/recreate that database or fixture tables. Never
reuse a deployment/customer URL. Prefer the supplied isolated CI job rather
than adding ad-hoc destructive tests to a shared SQL Server.

The new repository still needs a first actual GitHub run before configuring
required status checks. Local validation is not evidence that GitHub CI passed.
GitHub settings, CodeQL default setup and branch rules are external state, not
properties enforced merely by copying this directory.
