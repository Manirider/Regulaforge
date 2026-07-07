#!/bin/bash
# =============================================================================
# RegulaForge - Secrets Generation Script
# Usage: ./scripts/generate-secrets.sh [--output-dir .secrets]
# =============================================================================

set -euo pipefail

OUTPUT_DIR="${1:-.secrets}"
mkdir -p "$OUTPUT_DIR"

echo "🔐 Generating RegulaForge secrets..."
echo ""

# Generate random 64-char hex strings
generate_secret() {
    openssl rand -hex 32
}

generate_password() {
    openssl rand -base64 16 | tr -d '+/=' | cut -c1-20
}

# ─── Secrets ────────────────────────────────────────────────────────────────

SECRET_KEY=$(generate_secret)
DB_PASSWORD=$(generate_password)
REDIS_PASSWORD=$(generate_password)
RABBITMQ_PASSWORD=$(generate_password)
JWT_SECRET=$(generate_secret)
MLFLOW_TRACKING_PASSWORD=$(generate_password)
GRAFANA_ADMIN_PASSWORD=$(generate_password)
PROMETHEUS_PASSWORD=$(generate_password)

# ─── Write output ───────────────────────────────────────────────────────────

cat > "$OUTPUT_DIR/.env.secrets" << EOF
# =============================================================================
# RegulaForge - Production Secrets (auto-generated)
# WARNING: Keep this file secure! Never commit to version control.
# =============================================================================
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Application
SECRET_KEY=${SECRET_KEY}

# Database
POSTGRES_PASSWORD=${DB_PASSWORD}
DB_PASSWORD=${DB_PASSWORD}

# Cache
REDIS_PASSWORD=${REDIS_PASSWORD}

# Message Broker
RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD}

# JWT
JWT_SECRET_KEY=${JWT_SECRET}

# MLflow
MLFLOW_TRACKING_PASSWORD=${MLFLOW_TRACKING_PASSWORD}

# Monitoring
GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
PROMETHEUS_PASSWORD=${PROMETHEUS_PASSWORD}
EOF

cat > "$OUTPUT_DIR/.env.secrets.example" << EOF
# =============================================================================
# RegulaForge - Secrets Template
# Copy to .env.secrets and fill in your values
# =============================================================================

# Application - Generate with: openssl rand -hex 32
SECRET_KEY=change-me-to-a-random-hex-string

# Database
POSTGRES_PASSWORD=change-me-to-a-strong-password
DB_PASSWORD=\${POSTGRES_PASSWORD}

# Cache
REDIS_PASSWORD=change-me-to-a-strong-password

# Message Broker
RABBITMQ_DEFAULT_PASS=change-me-to-a-strong-password

# JWT
JWT_SECRET_KEY=change-me-to-a-random-hex-string

# AI/LLM
LLM_API_KEY=sk-your-openai-api-key

# Monitoring
SENTRY_DSN=https://key@sentry.io/project
GRAFANA_ADMIN_PASSWORD=change-me
PROMETHEUS_PASSWORD=change-me

# MLflow
MLFLOW_TRACKING_PASSWORD=change-me

# AWS (if used)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
EOF

echo "✅ Secrets generated:"
echo "   • $OUTPUT_DIR/.env.secrets     (actual secrets - PROTECT THIS FILE)"
echo "   • $OUTPUT_DIR/.env.secrets.example (template without values)"
echo ""
echo "⚠️  IMPORTANT:"
echo "   • Store .env.secrets in a password manager (1Password, LastPass, etc.)"
echo "   • For production, use HashiCorp Vault, AWS Secrets Manager, or SOPS"
echo "   • Never commit .env.secrets to version control"
echo ""
echo "📋 Summary:"
echo "   DB_PASSWORD:         ${DB_PASSWORD}"
echo "   GRAFANA_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}"
echo "   SECRET_KEY:          ${SECRET_KEY:0:16}... (truncated)"
