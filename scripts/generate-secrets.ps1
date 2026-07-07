# =============================================================================
# RegulaForge - Secrets Generation Script (PowerShell)
# Usage: .\scripts\generate-secrets.ps1 [-OutputDir .secrets]
# =============================================================================

param(
    [string]$OutputDir = ".secrets"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Generate-Secret {
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [System.BitConverter]::ToString($bytes).Replace("-", "").ToLower()
}

function Generate-Password {
    $bytes = New-Object byte[] 16
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [System.Convert]::ToBase64String($bytes).Replace("+", "").Replace("/", "").Substring(0, 20)
}

Write-Host "🔐 Generating RegulaForge secrets..." -ForegroundColor Cyan
Write-Host ""

$SECRET_KEY = Generate-Secret
$DB_PASSWORD = Generate-Password
$REDIS_PASSWORD = Generate-Password
$RABBITMQ_PASSWORD = Generate-Password
$JWT_SECRET = Generate-Secret
$MLFLOW_TRACKING_PASSWORD = Generate-Password
$GRAFANA_ADMIN_PASSWORD = Generate-Password
$PROMETHEUS_PASSWORD = Generate-Password

$timestamp = (Get-Date -Format "o")

@"
# =============================================================================
# RegulaForge - Production Secrets (auto-generated)
# WARNING: Keep this file secure! Never commit to version control.
# =============================================================================
# Generated: $timestamp

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
"@ | Out-File -FilePath "$OutputDir\.env.secrets" -Encoding UTF8

@"
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
"@ | Out-File -FilePath "$OutputDir\.env.secrets.example" -Encoding UTF8

Write-Host "✅ Secrets generated:" -ForegroundColor Green
Write-Host "   • $OutputDir\.env.secrets     (actual secrets - PROTECT THIS FILE)"
Write-Host "   • $OutputDir\.env.secrets.example (template without values)"
Write-Host ""
Write-Host "⚠️  IMPORTANT:" -ForegroundColor Yellow
Write-Host "   • Store .env.secrets in a password manager"
Write-Host "   • For production, use HashiCorp Vault or AWS Secrets Manager"
Write-Host "   • Never commit .env.secrets to version control"
Write-Host ""
Write-Host "📋 Summary:"
Write-Host "   DB_PASSWORD:         $DB_PASSWORD"
Write-Host "   GRAFANA_ADMIN_PASSWORD: $GRAFANA_ADMIN_PASSWORD"
