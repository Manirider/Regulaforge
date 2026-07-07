# Getting Started Guide

## Prerequisites

### Software
- **Python** 3.11 or later
- **PostgreSQL** 16 or later
- **Redis** 7 or later
- **Docker & Docker Compose** (optional, for containerized setup)
- **Git**
- **OpenAI API key** (for AI features)

### Verify Installation
```bash
python --version               # Python 3.11+
psql --version                 # psql 16+
redis-cli --version            # redis-cli 7+
docker --version               # Docker 24+
docker compose version         # Docker Compose v2+
```

## Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/regulaforge/regulaforge.git
cd regulaforge
```

### 2. Create Python Virtual Environment
```bash
cd backend
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
# Install Poetry (dependency manager)
pip install poetry

# Install all dependencies including dev
poetry install

# Or install production-only
poetry install --no-dev
```

### 4. Configure Environment Variables
```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your settings
# Minimum required changes:
#   REGULAFORGE_DB_URL - PostgreSQL connection string
#   REGULAFORGE_SECURITY_SECRET_KEY - JWT signing secret (min 32 chars)
#   REGULAFORGE_AI_LLM_API_KEY - Your OpenAI API key
```

### 5. Set Up the Database
```bash
# Create the database (as PostgreSQL superuser)
psql -U postgres -c "CREATE USER regulaforge WITH PASSWORD 'regulaforge';"
psql -U postgres -c "CREATE DATABASE regulaforge OWNER regulaforge;"

# Enable extensions
psql -U regulaforge -d regulaforge -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
psql -U regulaforge -d regulaforge -c "CREATE EXTENSION IF NOT EXISTS \"pg_trgm\";"
```

### 6. Run Database Migrations
```bash
alembic upgrade head

# Verify migration status
alembic current
```

### 7. Start the API Server
```bash
# Development mode with auto-reload
uvicorn regulaforge.interfaces.api.app:app --reload --host 0.0.0.0 --port 8000
```

### 8. Verify the API is Running
```bash
# Health check
curl http://localhost:8000/api/v1/health

# Expected response:
# {"status":"healthy","version":"0.1.0","environment":"development","database":"connected"}

# Open API documentation
open http://localhost:8000/api/v1/docs
```

## Docker Compose Setup

### Quick Start with Docker
```bash
# From the repository root
docker compose -f docker/docker-compose.yml up -d

# Run migrations
docker compose -f docker/docker-compose.yml run --rm migrate

# Verify
curl http://localhost:8000/api/v1/health

# View logs
docker compose -f docker/docker-compose.yml logs -f api

# Stop all services
docker compose -f docker/docker-compose.yml down
```

### Docker Compose Services
| Service | Container Name | Port |
|---|---|---|
| API Server | regulaforge-api | 8000 |
| PostgreSQL | regulaforge-db | 5432 |
| Redis | regulaforge-cache | 6379 |
| RabbitMQ | regulaforge-broker | 5672, 15672 |

## First API Calls

### 1. Create an Assessable Entity
```bash
curl -X POST http://localhost:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "name": "My Organization",
    "entity_type": "organization",
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "description": "Test organization"
  }'
```

### 2. Create a Regulation
```bash
curl -X POST http://localhost:8000/api/v1/regulations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "title": "Sample Data Protection Policy",
    "code": "SDPP-001",
    "description": "Internal data protection policy for testing",
    "category": "data_protection",
    "jurisdiction": "global",
    "issuing_body": "Internal Compliance",
    "effective_date": "2026-01-01"
  }'
```

### 3. Publish the Regulation
```bash
curl -X POST http://localhost:8000/api/v1/regulations/<regulation-id>/publish \
  -H "Authorization: Bearer <your-token>"
```

### 4. Create a Compliance Assessment
```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "title": "Initial Compliance Assessment",
    "entity_id": "<entity-id>",
    "regulation_ids": ["<regulation-id>"],
    "assessor_id": "00000000-0000-0000-0000-000000000001",
    "due_date": "2026-12-31",
    "scope_description": "Initial assessment test"
  }'
```

## Running Tests

### Test Categories
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=regulaforge --cov-report=term-missing

# Run specific test categories
pytest -m unit              # Unit tests (fast, no external deps)
pytest -m integration       # Integration tests (DB, Redis)
pytest -m e2e               # End-to-end tests (full stack)

# Run specific test file
pytest tests/unit/domain/test_regulation.py

# Run with verbose output
pytest -v
```

### Test Configuration
```bash
# Test database (auto-created by test fixtures)
REGULAFORGE_ENVIRONMENT=testing

# Run tests with specific database URL
REGULAFORGE_DB_URL=postgresql+asyncpg://regulaforge:regulaforge@localhost:5432/regulaforge_test pytest
```

### Linting and Type Checking
```bash
# Ruff linter
ruff check .
ruff check --fix .           # Auto-fix issues

# MyPy type checking
mypy src/regulaforge

# Format code
ruff format .
```

## Common Development Tasks

### Creating a New Migration
```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "add_new_table"

# Review the generated migration
cat alembic/versions/xxxx_add_new_table.py

# Apply the migration
alembic upgrade head
```

### Creating a New API Endpoint
1. Define request/response Pydantic schemas in the router file
2. Create the use case in `application/use_cases/`
3. Add repository method in `domain/repositories/`
4. Implement repository adapter in `infrastructure/persistence/adapters/`
5. Add the route to the router
6. Wire the dependency in `interfaces/api/dependencies.py`
7. Register the router in `interfaces/api/app.py`

### Adding a New Domain Entity
1. Create entity class in `domain/entities/`
2. Create value objects in `domain/value_objects/`
3. Define domain events in `domain/events/`
4. Create repository interface in `domain/repositories/`
5. Create SQLAlchemy model in `infrastructure/persistence/models/`
6. Create repository adapter in `infrastructure/persistence/adapters/`
7. Create use case(s) in `application/use_cases/`
8. Add API endpoints
9. Write unit and integration tests

### Debugging Tips
```bash
# Enable SQL query logging
REGULAFORGE_DB_ECHO=true uvicorn regulaforge.interfaces.api.app:app --reload

# Watch logs in development
docker compose -f docker/docker-compose.yml logs -f api

# Interactive database shell
docker compose -f docker/docker-compose.yml exec db psql -U regulaforge -d regulaforge

# Run Python with debugger
python -m debugpy --listen 0.0.0.0:5678 -m uvicorn regulaforge.interfaces.api.app:app --reload
```
