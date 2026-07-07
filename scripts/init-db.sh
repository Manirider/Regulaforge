#!/bin/bash
# =============================================================================
# RegulaForge - Database Initialization Script
# Runs on first deploy or migration
# =============================================================================

set -euo pipefail

echo "🔧 RegulaForge Database Initialization"
echo "========================================"

# Wait for database
echo "⏳ Waiting for PostgreSQL..."
./scripts/wait-for-it.sh db:5432 -t 60 -q
echo "✅ Database is ready"

# Run migrations
echo "⏳ Running Alembic migrations..."
alembic upgrade head
echo "✅ Migrations complete"

# Seed initial data (if configured)
if [ "${REGULAFORGE_SEED_DB:-}" = "true" ]; then
    echo "⏳ Seeding database..."
    python -m regulaforge.main seed
    echo "✅ Database seeded"
fi

echo "========================================"
echo "✅ Database initialization complete"
exit 0
