#!/bin/bash
# =============================================================================
# RegulaForge - MLflow entrypoint
# =============================================================================

set -euo pipefail

# If backend store URI is PostgreSQL, wait for it
if [[ "$MLFLOW_BACKEND_STORE_URI" == postgresql* ]]; then
    echo "Waiting for PostgreSQL backend..."
    DB_HOST=$(echo "$MLFLOW_BACKEND_STORE_URI" | sed -n 's/.*@\([^:/]*\).*/\1/p')
    DB_PORT=$(echo "$MLFLOW_BACKEND_STORE_URI" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_PORT=${DB_PORT:-5432}

    for i in $(seq 1 30); do
        if curl -s -o /dev/null "http://$DB_HOST:$DB_PORT" 2>/dev/null; then
            echo "PostgreSQL is ready."
            break
        fi
        echo "Waiting for PostgreSQL... ($i/30)"
        sleep 2
    done
fi

# Run MLflow
exec "$@"
