# Kubernetes Deployment Guide

## Cluster Requirements

### Node Specifications
| Node Pool | Instance Type | Min Nodes | Max Nodes | Purpose |
|---|---|---|---|---|
| System | 2 vCPU, 4 GB RAM | 2 | 3 | Ingress, monitoring, system components |
| Application | 4 vCPU, 8 GB RAM | 2 | 10 | API server pods |
| Data | 8 vCPU, 32 GB RAM | 3 | 6 | PostgreSQL, Redis, RabbitMQ (stateful) |

### Required Add-ons
- **Ingress Controller**: nginx-ingress or AWS ALB Ingress Controller
- **Certificate Manager**: cert-manager for TLS certificates
- **Metrics Server**: For HPA autoscaling
- **CSI Driver**: For persistent volumes (EBS, GCE PD, etc.)
- **Service Mesh** (optional): Linkerd or Istio for mTLS
- **External DNS** (optional): For automated DNS management

### Namespace Structure
```
regulaforge/          # Main application namespace
regulaforge-system/   # System components (monitoring, logging)
regulaforge-staging/  # Staging environment (optional)
```

## Installing with Helm

### Repository Setup
```bash
# Add the RegulaForge Helm repository
helm repo add regulaforge https://charts.regulaforge.io
helm repo update

# Search available versions
helm search repo regulaforge --versions
```

### Installation
```bash
# Create namespace
kubectl create namespace regulaforge

# Install with default values
helm install regulaforge regulaforge/regulaforge \
  --namespace regulaforge

# Install with custom values file
helm install regulaforge regulaforge/regulaforge \
  --namespace regulaforge \
  --values values-production.yaml

# Install specific version
helm install regulaforge regulaforge/regulaforge \
  --namespace regulaforge \
  --version 0.1.0 \
  --values values-production.yaml
```

### values-production.yaml Example
```yaml
global:
  environment: production
  appVersion: "0.1.0"

api:
  replicas: 3
  image:
    repository: regulaforge/api
    tag: 0.1.0
    pullPolicy: Always
  resources:
    requests:
      cpu: "1"
      memory: "2Gi"
    limits:
      cpu: "2"
      memory: "4Gi"
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80

database:
  enabled: true
  engine: postgresql
  version: "16"
  replicas: 1
  resources:
    requests:
      cpu: "2"
      memory: "8Gi"
  persistence:
    size: 100Gi
    storageClass: gp3

cache:
  enabled: true
  engine: redis
  version: "7"
  replicas: 3  # Redis cluster mode
  persistence:
    size: 10Gi
    storageClass: gp3

broker:
  enabled: true
  engine: rabbitmq
  version: "3.12"
  replicas: 3  # RabbitMQ cluster
  persistence:
    size: 20Gi
    storageClass: gp3

ingress:
  enabled: true
  hostname: api.regulaforge.io
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  tls: true

monitoring:
  prometheus:
    enabled: true
  grafana:
    enabled: true
    dashboards:
      - regulaforge-api-dashboard.json
      - regulaforge-business-dashboard.json
```

### Verification
```bash
# Check pods
kubectl -n regulaforge get pods
NAME                                  READY   STATUS    RESTARTS   AGE
regulaforge-api-6b7f8c9d8-abc12       1/1     Running   0          5m
regulaforge-api-6b7f8c9d8-def34       1/1     Running   0          5m
regulaforge-api-6b7f8c9d8-ghi56       1/1     Running   0          5m
regulaforge-db-0                       1/1     Running   0          6m
regulaforge-cache-0                    1/1     Running   0          6m
regulaforge-cache-1                    1/1     Running   0          5m
regulaforge-cache-2                    1/1     Running   0          5m
regulaforge-broker-0                   1/1     Running   0          6m

# Check services
kubectl -n regulaforge get svc

# Check ingress
kubectl -n regulaforge get ingress

# Test endpoint
curl https://api.regulaforge.io/api/v1/health
```

## Configuration Reference

### Helm Chart Values

| Parameter | Description | Default |
|---|---|---|
| `api.replicas` | Number of API replicas | `2` |
| `api.image.repository` | API image repository | `regulaforge/api` |
| `api.image.tag` | API image tag | `latest` |
| `api.resources.requests.cpu` | CPU request per pod | `500m` |
| `api.resources.requests.memory` | Memory request per pod | `1Gi` |
| `api.autoscaling.enabled` | Enable HPA | `false` |
| `api.autoscaling.minReplicas` | Minimum replicas | `2` |
| `api.autoscaling.maxReplicas` | Maximum replicas | `10` |
| `database.replicas` | Database replicas | `1` |
| `database.persistence.size` | Database volume size | `50Gi` |
| `cache.replicas` | Redis replicas | `1` |
| `cache.persistence.size` | Redis volume size | `10Gi` |
| `broker.replicas` | RabbitMQ replicas | `1` |
| `broker.persistence.size` | RabbitMQ volume size | `10Gi` |
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.hostname` | Ingress hostname | `""` |
| `monitoring.prometheus.enabled` | Enable Prometheus | `false` |
| `monitoring.grafana.enabled` | Enable Grafana | `false` |

### ConfigMap Structure
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: regulaforge-config
  namespace: regulaforge
data:
  REGULAFORGE_ENVIRONMENT: "production"
  REGULAFORGE_LOG_LEVEL: "INFO"
  REGULAFORGE_LOG_JSON: "true"
  REGULAFORGE_DB_POOL_SIZE: "20"
  REGULAFORGE_SECURITY_CORS_ORIGINS: '["https://app.regulaforge.io"]'
  REGULAFORGE_AI_LLM_MODEL: "gpt-4-turbo"
```

## Scaling Guidelines

### Horizontal Pod Autoscaling (HPA)
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: regulaforge-api
  namespace: regulaforge
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: regulaforge-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### Scaling Triggers
| Metric | Threshold | Action |
|---|---|---|
| CPU utilization | > 70% for 3 min | Scale up |
| Memory utilization | > 80% for 3 min | Scale up |
| Request latency p99 | > 500ms for 5 min | Scale up |
| Queue depth (RabbitMQ) | > 1000 messages | Scale up consumers |
| CPU utilization | < 30% for 10 min | Scale down |

## Troubleshooting

### Common Issues

**Pod CrashLoopBackOff:**
```bash
# Check logs
kubectl -n regulaforge logs -f deployment/regulaforge-api

# Check events
kubectl -n regulaforge describe pod regulaforge-api-xxx

# Common causes:
# - Missing secrets (check secret exists)
# - Database unreachable (check db service)
# - Invalid configuration (check configmap)
```

**Database Connection Errors:**
```bash
# Verify database pod is running
kubectl -n regulaforge exec -it regulaforge-db-0 -- pg_isready

# Check connection string secret
kubectl -n regulaforge get secret regulaforge-secrets -o yaml

# Port-forward for manual testing
kubectl -n regulaforge port-forward svc/regulaforge-db 5432:5432
```

**Ingress Not Working:**
```bash
# Check ingress status
kubectl -n regulaforge describe ingress regulaforge

# Check service endpoints
kubectl -n regulaforge get endpoints regulaforge-api

# Verify TLS certificate
kubectl -n regulaforge get certificate
```

**Redis/RabbitMQ Connection Issues:**
```bash
# Test Redis
kubectl -n regulaforge exec -it deployment/regulaforge-api -- redis-cli -h regulaforge-cache ping

# Test RabbitMQ
kubectl -n regulaforge exec -it deployment/regulaforge-api -- \
  curl -s http://regulaforge-broker:15672/api/health/checks/alarms
```

## Upgrade Procedure

### Rolling Upgrade

```bash
# 1. Backup database
kubectl -n regulaforge exec regulaforge-db-0 -- pg_dump -U regulaforge -F c > pre-upgrade-backup.dump

# 2. Update Helm repository
helm repo update

# 3. Upgrade with new version
helm upgrade regulaforge regulaforge/regulaforge \
  --namespace regulaforge \
  --values values-production.yaml \
  --version 0.2.0

# 4. Monitor rollout
kubectl -n regulaforge rollout status deployment/regulaforge-api

# 5. Run migrations (if applicable)
kubectl -n regulaforge create job --from=cronjob/regulaforge-migrate migrate-manual

# 6. Verify health
curl https://api.regulaforge.io/api/v1/health

# 7. Verify business functionality
pytest tests/e2e/ --url https://api.regulaforge.io
```

### Rollback Procedure
```bash
# Rollback to previous revision
helm rollback regulaforge 1 --namespace regulaforge

# Or rollback to specific revision
helm rollback regulaforge <revision-number> --namespace regulaforge

# Verify rollback
kubectl -n regulaforge rollout status deployment/regulaforge-api
```

### Database Migration Strategy
- Migrations run as a pre-upgrade Kubernetes Job
- Always test migrations on staging before production
- Migrations are backward-compatible for one version
- Zero-downtime: blue-green deployment pattern for schema changes
- Complex migrations use the expand-migrate-contract pattern:
  1. Expand: Add new columns/tables (backward-compatible)
  2. Migrate: Backfill data in batches
  3. Contract: Remove old columns after no references remain
