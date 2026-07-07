# Deployment Overview

## Prerequisites

### Software Requirements
- **Python** 3.11+
- **PostgreSQL** 16+ with `pg_trgm` extension
- **Redis** 7+
- **RabbitMQ** 3.12+ with management plugin
- **Docker** 24+ (for containerized deployment)
- **Kubernetes** 1.28+ (for orchestrated deployment)
- **Helm** 3.12+ (for K8s chart installation)

### System Requirements

| Environment | CPU | RAM | Disk | Network |
|---|---|---|---|---|
| Development | 2 cores | 4 GB | 20 GB SSD | 100 Mbps |
| Staging | 4 cores | 8 GB | 50 GB SSD | 1 Gbps |
| Production (minimum) | 8 cores | 16 GB | 100 GB SSD | 1 Gbps |
| Production (recommended) | 16 cores | 32 GB | 500 GB SSD | 10 Gbps |

### External Dependencies
- **AI Provider**: OpenAI API key (or Anthropic/Azure) for AI compliance features
- **Sentry DSN** (optional): For error tracking
- **Object Storage**: S3-compatible storage for document file persistence (production)
- **SMTP Server**: For email notifications

## Infrastructure Requirements

### Network Topology (Production)

```
Internet
   │
   ▼
┌─────────────────┐
│  CDN / WAF      │  CloudFront / Cloudflare
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Load Balancer  │  ALB / Nginx (TLS termination)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  API Service    │  FastAPI (multiple replicas)
│  :8000          │
└────────┬────────┘
         │
    ┌────┼────┬────┬────┐
    ▼    ▼    ▼    ▼    ▼
  ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──────┐
  │PG│ │Rd│ │MQ│ │FS│ │  AI  │
  │  │ │  │ │  │ │  │ │ API  │
  └──┘ └──┘ └──┘ └──┘ └──────┘
```

### Port Mapping

| Service | Port | Protocol | Description |
|---|---|---|---|
| API Server | 8000 | HTTP/REST | Main API endpoint |
| PostgreSQL | 5432 | TCP | Database |
| Redis | 6379 | TCP | Cache and rate limiting |
| RabbitMQ | 5672 | TCP | Message broker |
| RabbitMQ Mgmt | 15672 | HTTP | Management UI |
| Prometheus | 9090 | HTTP | Metrics |
| Grafana | 3000 | HTTP | Dashboards |

## Deployment Options

### Option 1: Docker Compose (Simplest)

```bash
# Clone the repository
git clone https://github.com/regulaforge/regulaforge.git
cd regulaforge

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start all services
docker compose -f docker/docker-compose.yml up -d

# Run database migrations
docker compose -f docker/docker-compose.yml run --rm migrate

# Verify health
curl http://localhost:8000/api/v1/health
```

### Option 2: Kubernetes (Production)

```bash
# Create namespace
kubectl apply -f k8s/base/namespace.yaml

# Install with Helm
helm repo add regulaforge https://charts.regulaforge.io
helm install regulaforge regulaforge/regulaforge \
  --namespace regulaforge \
  --values values-production.yaml

# Verify deployment
kubectl -n regulaforge get pods
kubectl -n regulaforge get svc
```

### Option 3: Bare Metal / VM

```bash
# System dependencies (Ubuntu/Debian)
sudo apt update && sudo apt install -y \
  python3.11 python3.11-venv postgresql-16 redis-server rabbitmq-server nginx

# Clone and configure
git clone https://github.com/regulaforge/regulaforge.git
cd regulaforge/backend

# Python setup
python3.11 -m venv .venv
source .venv/bin/activate
pip install poetry
poetry install --no-dev

# Configure and run
cp .env.example .env
# Edit .env

# Alembic migrations
alembic upgrade head

# Start with systemd or supervisor
uvicorn regulaforge.interfaces.api.app:app \
  --host 0.0.0.0 --port 8000 \
  --workers 4 \
  --log-level info
```

## Environment Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `REGULAFORGE_ENVIRONMENT` | No | `development` | `development`, `staging`, `production`, `testing` |
| `REGULAFORGE_DEBUG` | No | `false` | Enable debug mode |
| `REGULAFORGE_LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `REGULAFORGE_LOG_JSON` | No | `true` | JSON log formatting |
| `REGULAFORGE_API_HOST` | No | `0.0.0.0` | API bind address |
| `REGULAFORGE_API_PORT` | No | `8000` | API port |
| `REGULAFORGE_DB_URL` | Yes | *default* | PostgreSQL async DSN |
| `REGULAFORGE_DB_POOL_SIZE` | No | `20` | Connection pool size |
| `REGULAFORGE_CACHE_URL` | Yes | *default* | Redis DSN |
| `REGULAFORGE_BROKER_URL` | Yes | *default* | RabbitMQ AMQP DSN |
| `REGULAFORGE_SECURITY_SECRET_KEY` | **Yes** | *placeholder* | JWT signing secret (min 32 chars) |
| `REGULAFORGE_SECURITY_CORS_ORIGINS` | No | `["*"]` | Allowed CORS origins |
| `REGULAFORGE_AI_LLM_API_KEY` | **Yes** | - | OpenAI/Anthropic API key |
| `REGULAFORGE_AI_LLM_MODEL` | No | `gpt-4-turbo` | LLM model name |
| `REGULAFORGE_MONITORING_SENTRY_DSN` | No | - | Sentry error tracking DSN |

### .env Example
```bash
# Environment
REGULAFORGE_ENVIRONMENT=development
REGULAFORGE_DEBUG=true
REGULAFORGE_LOG_LEVEL=DEBUG

# Database
REGULAFORGE_DB_URL=postgresql+asyncpg://regulaforge:password@localhost:5432/regulaforge

# Cache
REGULAFORGE_CACHE_URL=redis://localhost:6379/0

# Message Broker
REGULAFORGE_BROKER_URL=amqp://guest:guest@localhost:5672/

# Security
REGULAFORGE_SECURITY_SECRET_KEY=your-32-char-minimum-secret-key-here!

# AI
REGULAFORGE_AI_LLM_API_KEY=sk-your-openai-api-key

# Monitoring (optional)
REGULAFORGE_MONITORING_SENTRY_DSN=
```

## Database Setup and Migrations

### Initial Setup
```sql
-- Create database and user (as PostgreSQL superuser)
CREATE USER regulaforge WITH PASSWORD 'your-password';
CREATE DATABASE regulaforge OWNER regulaforge;

-- Enable required extensions
\c regulaforge
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

### Running Migrations
```bash
# Local
alembic upgrade head

# Docker
docker compose -f docker/docker-compose.yml run --rm migrate

# Check status
alembic current

# Rollback one version
alembic downgrade -1

# Create a new migration
alembic revision --autogenerate -m "description"
```

### Migration Structure
```
backend/alembic/
├── env.py                    # Alembic environment config
├── alembic.ini               # Alembic configuration
└── versions/
    ├── 0001_initial_schema.py    # Core tables
    ├── 0002_add_audit_logs.py    # Audit entries
    ├── 0003_add_ai_results.py    # AI analysis results
    └── ...
```

## Secrets Setup

### Production Secrets Management

**Kubernetes Secrets:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: regulaforge-secrets
  namespace: regulaforge
type: Opaque
stringData:
  secret-key: "your-32-char-minimum-secret-key-here"
  db-password: "your-db-password"
  llm-api-key: "sk-your-openai-api-key"
  sentry-dsn: "https://..."
```

**Docker Secrets:**
```bash
# Create secrets
echo "your-secret-key" | docker secret create regulaforge_secret_key -
echo "your-db-password" | docker secret create regulaforge_db_password -

# Reference in docker-compose.yml
secrets:
  - regulaforge_secret_key
  - regulaforge_db_password
```

### Local Development
```bash
# Copy and edit template (NEVER commit .env)
cp .env.example .env
# Edit with local values
```

## Monitoring Setup

See [Monitoring Guide](monitoring.md) for full details.

### Quick Start
```bash
# Prometheus + Grafana with Docker
docker compose -f docker/docker-compose.monitoring.yml up -d

# Access Grafana at http://localhost:3000 (admin/admin)
# Import dashboards from /infrastructure/grafana/dashboards/
```

### Health Check Endpoint
```bash
curl http://localhost:8000/api/v1/health

# Response
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "production",
  "database": "connected"
}
```

## Backup and Disaster Recovery

### Backup Strategy

| Component | Method | Frequency | Retention |
|---|---|---|---|
| PostgreSQL | `pg_dump` / WAL archiving | Daily full + continuous WAL | 30 days daily, 12 monthly |
| File Storage | S3 sync / rsync | Hourly | 7 days |
| Redis | RDB snapshots | Every 5 minutes | 24 hours |
| RabbitMQ | Definition export | On config change | Indefinite |
| Application Config | Git (VCS) | On change | Full history |

### Database Backup Commands
```bash
# Full backup
pg_dump -h localhost -U regulaforge -F c -f backup_$(date +%Y%m%d).dump regulaforge

# Restore
pg_restore -h localhost -U regulaforge -d regulaforge -c backup_20260704.dump

# Automated cron (daily)
0 2 * * * pg_dump -h localhost -U regulaforge -F c -f /backups/daily/regulaforge_$(date +\%Y\%m\%d).dump regulaforge
```

### Disaster Recovery Plan

| Scenario | RTO | RPO | Recovery Procedure |
|---|---|---|---|
| Database corruption | 4 hours | 24 hours | Restore from latest full backup + WAL replay |
| Region failure | 8 hours | 1 hour | Failover to DR region, promote read replica |
| Accidental data loss | 2 hours | 5 minutes | PITR to specific timestamp |
| Full site failure | 24 hours | 1 hour | Restore from offsite backup in new region |

### Recovery Steps
```bash
# 1. Provision new infrastructure
terraform apply -auto-approve

# 2. Restore database
pg_restore -h new-db -U regulaforge -d regulaforge -c latest_backup.dump

# 3. Restore file storage
aws s3 sync s3://backup-bucket/documents/ /data/regulaforge/uploads/

# 4. Deploy application
kubectl apply -f k8s/production/

# 5. Verify integrity
curl https://api.regulaforge.io/api/v1/health
```
