#!/bin/bash
set -e

# Wait for a real database connection (P1-13).
#
# This used to call create_db.py in the retry loop, but create_db.py caught
# every exception internally and always returned exit code 0 - so this loop
# "succeeded" on its first attempt even when SQL Server was not reachable yet,
# and `alembic upgrade head` failed hard immediately after. wait_for_db.py
# does one job - report readiness truthfully - so the retry here is real.
echo "Waiting for SQL Server to be ready..."
max_retries=30
count=0
while [ $count -lt $max_retries ]; do
    if python wait_for_db.py; then
        echo "Database is reachable."
        break
    else
        echo "Database not ready yet. Retrying in 2 seconds... ($((count+1))/$max_retries)"
        sleep 2
        count=$((count+1))
    fi
done

if [ $count -eq $max_retries ]; then
    echo "Error: Could not connect to database after $max_retries attempts."
    exit 1
fi

# Now that the server is reachable, create the application database/login if
# they do not exist yet. Runs once - it is not a readiness probe.
echo "Ensuring application database and login exist..."
python create_db.py

# Apply schema migrations (see docs/adr/ADR-0001-schema-migrations-alembic.md).
# create_db.py above only ensures the database/login exist; it no longer
# creates tables.
echo "Applying migrations..."
alembic upgrade head

# Start the application
exec "$@"
