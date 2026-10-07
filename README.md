# WebQuery

A self-hosted SQL workspace for governed database access. WebQuery combines a
React query console with scoped permissions, risk review, audit records and
driver-level query cancellation.

Built as an engineering/portfolio project and a foundation for private-network
deployments. It is **not a production-certified or shared multi-tenant SaaS**.

## What it does

- Query registered SQL Server, PostgreSQL and MySQL targets using separate
  read/write/DDL credential tiers.
- Manage users, activation and target access with platform OWNER and
  database-scoped ADMIN roles.
- Save workspaces, review risky SQL, apply table-aware full masking and keep
  traceable audit records. Optional Slack integration shares the approval flow.
- Stream bounded read results, report truncation and export displayed data as
  CSV/XLSX.
- Cancel your running SQL from Studio, workspace execution or admin preview;
  the UI waits for target execution to finish, not just HTTP acceptance.

The SQL analyzer and result masking are not substitutes for least-privilege
target accounts. Cancellation has real MSSQL coverage; PostgreSQL/MySQL
live-driver verification and other limits are listed in
[implemented features](docs/features.md).

## Stack and layout

Python/FastAPI, SQLAlchemy + Alembic, Redis, React/TypeScript + Vite, CodeMirror,
Tailwind and nginx. CI/Docker use Python 3.11 and Node 24. SQL Server requires
system ODBC Driver 18; the metadata database is separate from query targets.

```text
web_api/       Backend domains, tests, migrations and owner bootstrap
frontend/      React application, shared components and design contract
docs/          Consolidated behavior, architecture, setup and remaining work
.github/       Backend/frontend/MSSQL validation workflow
```

## Start locally

For an isolated Docker development environment:

```bash
git clone https://github.com/erdemdnmz2/WebQuery.git
cd WebQuery
cp .env.example .env
```

Fill the blank secrets and database credentials using the
[configuration reference](docs/configuration.md). For local **HTTP only**, set
`DEBUG=true` and `COOKIE_SECURE=false`. The example intentionally fails startup
until required values are supplied; never commit `.env`.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db redis
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -it web \
  python -m scripts.bootstrap_owner --email owner@example.com --username owner
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

The one-off command provisions metadata, runs migrations and prompts for the
first OWNER password. An empty installation needs this before API startup.
Open `http://localhost`, then register targets and grant roles. The bundled SQL
Server bootstrap shares its SA/application password and interpolates its URL;
see the documented limitations before using it beyond local development.

For native setup, Vite port **3000**, driver requirements and full verification
commands, see [development](docs/development.md). Production needs HTTPS,
restricted ingress, verified proxy trust, independent secrets and restore tests;
the supplied HTTP Compose topology alone does not provide those guarantees.

## Validation

```bash
# From web_api/, with the backend environment activated:
env -u MSSQL_TEST_URL -u MSSQL_CI python -m pytest -q

# From frontend/:
npm ci
npm run typecheck
npm run build

# From repository root:
python3 scripts/check_repository.py
python3 -m unittest discover -s scripts/tests -v
```

CI also checks correctness lint, frontend API/contrast/export audits, dependency
advisories and a disposable real SQL Server/Redis integration environment.
Normal backend tests use SQLite/doubles; service-dependent tests are skipped
without their explicit CI configuration. There is no frontend behavioral test
command on this baseline. Local results do not establish remote CI success.

## Documentation and contribution

See the [documentation map](docs/README.md),
[remaining implementation plan](docs/implementation-plan.md),
[contribution guide](CONTRIBUTING.md) and [security policy](SECURITY.md).
Historical/duplicate documents were consolidated against the running code;
[migration analysis](docs/migration-analysis.md) preserves their disposition.

## License

[Apache License 2.0](LICENSE). Imported legacy code retains its original
[MIT notice](licenses/WebQuery-legacy-MIT.txt); see [NOTICE](NOTICE).
Dependencies retain their respective licenses.
