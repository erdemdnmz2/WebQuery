#!/bin/bash
set -e

# Wait for database connection (Retry mechanism)
echo "Waiting for SQL Server to be ready..."
max_retries=30
count=0
while [ $count -lt $max_retries ]; do
    if python create_db.py; then
        echo "Database initialized successfully."
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

# Apply schema migrations (see docs/adr/ADR-0001-schema-migrations-alembic.md).
# create_db.py above only ensures the database/login exist; it no longer
# creates tables.
echo "Applying migrations..."
alembic upgrade head

# Start the application
exec "$@"
