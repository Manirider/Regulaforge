# Monitoring and Observability

## Prometheus Metrics

### Metrics Endpoint
The API server exposes Prometheus metrics at:
```
GET /metrics
```

### Application Metrics

**API Metrics:**
```
# HELP regulaforge_http_requests_total Total HTTP requests
# TYPE regulaforge_http_requests_total counter
regulaforge_http_requests_total{method="POST",endpoint="/api/v1/regulations",status_code="201"} 150

# HELP regulaforge_http_request_duration_seconds HTTP request duration
# TYPE regulaforge_http_request_duration_seconds histogram
regulaforge_http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/regulations",le="0.005"} 42
regulaforge_http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/regulations",le="0.01"} 128
regulaforge_http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/regulations",le="0.025"} 245
regulaforge_http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/regulations",le="0.05"} 312
regulaforge_http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/regulations",le="+Inf"} 340
regulaforge_http_request_duration_seconds_count{method="GET",endpoint="/api/v1/regulations"} 340

# HELP regulaforge_http_active_requests Number of active HTTP requests
# TYPE regulaforge_http_active_requests gauge
regulaforge_http_active_requests 12
```

**Business Metrics:**
```
# HELP regulaforge_regulations_total Total regulations created
# TYPE regulaforge_regulations_total counter
regulaforge_regulations_total{category="data_protection"} 25
regulaforge_regulations_total{category="cybersecurity"} 12
regulaforge_regulations_total{category="financial"} 8

# HELP regulaforge_assessments_total Total compliance assessments
# TYPE regulaforge_assessments_total counter
regulaforge_assessments_total{status="scheduled"} 45
regulaforge_assessments_total{status="in_progress"} 12
regulaforge_assessments_total{status="completed"} 230

# HELP regulaforge_findings_total Total compliance findings
# TYPE regulaforge_findings_total counter
regulaforge_findings_total{risk_level="critical"} 3
regulaforge_findings_total{risk_level="high"} 15
regulaforge_findings_total{risk_level="medium"} 42
regulaforge_findings_total{risk_level="low"} 88

# HELP regulaforge_entities_total Total assessable entities
# TYPE regulaforge_entities_total gauge
regulaforge_entities_total{entity_type="organization"} 5
regulaforge_entities_total{entity_type="system"} 23
regulaforge_entities_total{entity_type="process"} 15
```

**AI Metrics:**
```
# HELP regulaforge_ai_requests_total Total AI processing requests
# TYPE regulaforge_ai_requests_total counter
regulaforge_ai_requests_total{operation="regulation_analysis",provider="openai"} 180

# HELP regulaforge_ai_request_duration_seconds AI request duration in seconds
# TYPE regulaforge_ai_request_duration_seconds histogram
regulaforge_ai_request_duration_seconds_bucket{operation="compliance_assessment",le="1.0"} 15
regulaforge_ai_request_duration_seconds_bucket{operation="compliance_assessment",le="5.0"} 62
regulaforge_ai_request_duration_seconds_bucket{operation="compliance_assessment",le="10.0"} 85
regulaforge_ai_request_duration_seconds_bucket{operation="compliance_assessment",le="+Inf"} 92

# HELP regulaforge_ai_token_usage_total Total AI token usage
# TYPE regulaforge_ai_token_usage_total counter
regulaforge_ai_token_usage_total{model="gpt-4-turbo",type="prompt"} 2450000
regulaforge_ai_token_usage_total{model="gpt-4-turbo",type="completion"} 890000
```

**Database Metrics:**
```
# HELP regulaforge_db_connection_pool_size Database connection pool size
# TYPE regulaforge_db_connection_pool_size gauge
regulaforge_db_connection_pool_size 18

# HELP regulaforge_db_query_duration_seconds Database query duration
# TYPE regulaforge_db_query_duration_seconds histogram
regulaforge_db_query_duration_seconds_bucket{operation="select",le="0.001"} 1500
regulaforge_db_query_duration_seconds_bucket{operation="select",le="0.01"} 3200
regulaforge_db_query_duration_seconds_bucket{operation="select",le="0.1"} 3400
regulaforge_db_query_duration_seconds_bucket{operation="select",le="+Inf"} 3410
```

## Grafana Dashboards

### API Performance Dashboard

```json
{
  "dashboard": {
    "title": "RegulaForge - API Performance",
    "timezone": "utc",
    "panels": [
      {
        "title": "Request Rate (RPS)",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(regulaforge_http_requests_total[5m]))",
            "legendFormat": "Total"
          },
          {
            "expr": "sum(rate(regulaforge_http_requests_total{status_code=~\"5..\"}[5m]))",
            "legendFormat": "Errors (5xx)"
          }
        ]
      },
      {
        "title": "P99 Latency by Endpoint",
        "type": "heatmap",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, sum(rate(regulaforge_http_request_duration_seconds_bucket[5m])) by (le, endpoint))",
            "legendFormat": "{{endpoint}}"
          }
        ]
      },
      {
        "title": "Active Requests",
        "type": "singlestat",
        "targets": [
          {
            "expr": "regulaforge_http_active_requests"
          }
        ]
      },
      {
        "title": "HTTP Error Rate by Status Code",
        "type": "pie",
        "targets": [
          {
            "expr": "sum(rate(regulaforge_http_requests_total{status_code=~\"4..\"}[5m])) by (status_code)",
            "legendFormat": "{{status_code}}"
          },
          {
            "expr": "sum(rate(regulaforge_http_requests_total{status_code=~\"5..\"}[5m])) by (status_code)",
            "legendFormat": "{{status_code}}"
          }
        ]
      },
      {
        "title": "Rate Limit Exhaustion",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(regulaforge_http_requests_total{status_code=\"429\"}[5m]))",
            "legendFormat": "429 Rate Limited"
          }
        ]
      }
    ],
    "rows": [
      {
        "title": "Database",
        "panels": [
          {
            "title": "DB Connection Pool",
            "type": "graph",
            "targets": [
              {
                "expr": "regulaforge_db_connection_pool_size",
                "legendFormat": "Active Connections"
              }
            ]
          },
          {
            "title": "DB Query Duration (P99)",
            "type": "graph",
            "targets": [
              {
                "expr": "histogram_quantile(0.99, sum(rate(regulaforge_db_query_duration_seconds_bucket[5m])) by (le, operation))",
                "legendFormat": "{{operation}}"
              }
            ]
          }
        ]
      },
      {
        "title": "AI",
        "panels": [
          {
            "title": "AI Request Rate",
            "type": "graph",
            "targets": [
              {
                "expr": "sum(rate(regulaforge_ai_requests_total[5m])) by (operation)",
                "legendFormat": "{{operation}}"
              }
            ]
          },
          {
            "title": "AI Token Usage (Daily)",
            "type": "bargauge",
            "targets": [
              {
                "expr": "sum(increase(regulaforge_ai_token_usage_total[24h])) by (type)",
                "legendFormat": "{{type}}"
              }
            ]
          },
          {
            "title": "AI Latency (P95)",
            "type": "graph",
            "targets": [
              {
                "expr": "histogram_quantile(0.95, sum(rate(regulaforge_ai_request_duration_seconds_bucket[5m])) by (le, operation))",
                "legendFormat": "{{operation}}"
              }
            ]
          },
          {
            "title": "Hallucination Rate",
            "type": "graph",
            "targets": [
              {
                "expr": "regulaforge_ai_hallucination_rate",
                "legendFormat": "Hallucination Rate"
              }
            ]
          }
        ]
      },
      {
        "title": "Business KPIs",
        "panels": [
          {
            "title": "Regulations by Category",
            "type": "pie",
            "targets": [
              {
                "expr": "sum(regulaforge_regulations_total) by (category)",
                "legendFormat": "{{category}}"
              }
            ]
          },
          {
            "title": "Assessments by Status",
            "type": "pie",
            "targets": [
              {
                "expr": "sum(regulaforge_assessments_total) by (status)",
                "legendFormat": "{{status}}"
              }
            ]
          },
          {
            "title": "Findings by Risk Level",
            "type": "bargauge",
            "targets": [
              {
                "expr": "sum(regulaforge_findings_total) by (risk_level)",
                "legendFormat": "{{risk_level}}"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

### SLO Dashboard
```json
{
  "panels": [
    {
      "title": "API Availability (30d SLO)",
      "type": "singlestat",
      "targets": [
        {
          "expr": "sum(rate(regulaforge_http_requests_total{status_code!~\"5..\"}[30d])) / sum(rate(regulaforge_http_requests_total[30d])) * 100",
          "legendFormat": "Availability"
        }
      ]
    },
    {
      "title": "API Latency P99 (30d SLO)",
      "type": "singlestat",
      "targets": [
        {
          "expr": "histogram_quantile(0.99, sum(rate(regulaforge_http_request_duration_seconds_bucket[30d])) by (le))",
          "legendFormat": "P99 Latency"
        }
      ]
    },
    {
      "title": "Error Budget Remaining (30d)",
      "type": "singlestat",
      "targets": [
        {
          "expr": "max(0, (1 - (sum(rate(regulaforge_http_requests_total{status_code=~\"5..\"}[30d])) / sum(rate(regulaforge_http_requests_total[30d])))) - 0.999) * 43200 * 0.001",
          "legendFormat": "Error Budget (hours)"
        }
      ]
    }
  ]
}
```

## Log Aggregation

### JSON Log Format (Structured Logging)
```json
{
  "timestamp": "2026-07-04T12:00:00.123456Z",
  "level": "INFO",
  "logger": "regulaforge.application.use_cases.regulation_use_cases",
  "message": "Regulation created: id=abc-123 code=GDPR",
  "module": "regulation_use_cases",
  "function": "execute",
  "line": 89,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "environment": "production",
  "service": "regulaforge-api",
  "version": "0.1.0",
  "extra": {
    "regulation_id": "abc-123",
    "code": "GDPR"
  }
}
```

### Log Levels
| Level | Usage |
|---|---|
| `DEBUG` | Detailed debugging information (development only) |
| `INFO` | Business operations (entity created, assessment started) |
| `WARNING` | Unexpected but handled conditions (rate limit near threshold) |
| `ERROR` | Error conditions that don't crash the application |
| `CRITICAL` | System-level failures requiring immediate attention |

### Log Shipping (ELK Stack)
```yaml
# Filebeat configuration
filebeat.inputs:
- type: container
  paths:
    - /var/log/containers/regulaforge*.log
  json.keys_under_root: true
  json.add_error_key: true

output.elasticsearch:
  hosts: ["https://elasticsearch:9200"]
  index: "regulaforge-logs-%{+yyyy.MM.dd}"
  username: "${ES_USERNAME}"
  password: "${ES_PASSWORD}"
```

## Distributed Tracing (OpenTelemetry)

### Configuration
```python
# settings.py
class MonitoringConfig(BaseSettings):
    enable_opentelemetry: bool = Field(default=False)
    otlp_endpoint: Optional[str] = Field(default=None)
```

### Trace Context Propagation
```
Client Request
  │
  ├── Correlation ID: 550e8400-e29b-41d4-a716-446655440000
  │
  ├── API Gateway
  │     └── Span: HTTP POST /api/v1/assessments
  │           │
  │           ├── Auth Middleware
  │           │     └── Span: JWT Verification (3ms)
  │           │
  │           ├── CreateAssessment Use Case
  │           │     ├── Span: Validate Entity (5ms)
  │           │     ├── Span: Validate Regulations (8ms)
  │           │     ├── Span: Save to Database (12ms)
  │           │     └── Span: Publish Events (2ms)
  │           │
  │           └── Response (200 OK)
  │
  └── Event: assessment.requested
        └── Consumer: Notification Service
              └── Span: Send Email Notification (50ms)
```

### Span Attributes
```python
# Example: instrumenting a use case
with tracer.start_as_current_span("create_assessment") as span:
    span.set_attribute("assessment.title", title)
    span.set_attribute("entity.id", str(entity_id))
    span.set_attribute("regulation.count", len(regulation_ids))
    span.set_attribute("user.id", str(assessor_id))
    
    # Business logic
    result = await self.execute_internal(...)
    
    span.set_attribute("assessment.id", str(result.id))
    span.set_status(Status(StatusCode.OK))
```

## Alerting Rules

### Prometheus Alert Rules
```yaml
groups:
  - name: regulaforge-api
    rules:
      - alert: HighErrorRate
        expr: rate(regulaforge_http_requests_total{status_code=~"5.."}[5m]) / rate(regulaforge_http_requests_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "API error rate above 1%"
          description: "Error rate is {{ $value | humanizePercentage }} over last 5 minutes"

      - alert: HighLatency
        expr: histogram_quantile(0.99, sum(rate(regulaforge_http_request_duration_seconds_bucket[5m])) by (le)) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency above 2 seconds"

      - alert: DatabaseConnectionLow
        expr: regulaforge_db_connection_pool_size < 5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool running low"

      - alert: HighAIHallucinationRate
        expr: regulaforge_ai_hallucination_rate{severity="critical"} > 0.05
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "AI hallucination rate above 5%"

      - alert: HighRateLimitExhaustion
        expr: rate(regulaforge_http_requests_total{status_code="429"}[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Rate limit exhaustion rate above 10 req/s"

  - name: regulaforge-business
    rules:
      - alert: AssessmentOverdue
        expr: time() - regulaforge_last_assessment_completion{entity="..."} > 7776000  # 90 days
        labels:
          severity: warning
        annotations:
          summary: "Entity assessment overdue by {{ $value | humanizeDuration }}"

      - alert: CriticalFindingsThreshold
        expr: regulaforge_findings_total{risk_level="critical"} > 5
        for: 24h
        labels:
          severity: critical
        annotations:
          summary: "More than 5 critical compliance findings"
```

## SLO/SLI Definitions

### Service Level Objectives

| SLO | Target | Measurement | Window |
|---|---|---|---|
| API Availability | 99.9% | Request success rate (non-5xx / total) | 30 days rolling |
| API Latency (P99) | < 2 seconds | HTTP request duration | 30 days rolling |
| API Latency (P95) | < 500ms | HTTP request duration | 30 days rolling |
| AI Analysis Accuracy | > 95% | Human review pass rate | 7 days rolling |
| AI Hallucination Rate | < 2% | Hallucination detector critical verdicts | 7 days rolling |

### Service Level Indicators (SLIs)

**Availability SLI:**
```
Availability = successful_requests / total_requests
  where successful_requests = HTTP status != 5xx
  Target: >= 0.999 (99.9%)
```

**Latency SLI:**
```
P99 Latency = 0.99th percentile of http_request_duration_seconds
  Target: < 2 seconds
```

**AI Accuracy SLI:**
```
AI Accuracy = ai_predictions_passing_review / total_ai_predictions
  Target: >= 0.95 (95%)
```

**Hallucination Rate SLI:**
```
Hallucination Rate = ai_responses_with_critical_hallucinations / total_ai_responses
  Target: <= 0.02 (2%)
```

### Error Budget Calculation
```
Error Budget (30 days) = (1 - SLO_target) * total_seconds_in_period
  = (1 - 0.999) * 2,592,000
  = 2,592 seconds (43.2 minutes)

Error Budget Consumption = (1 - actual_availability) * total_seconds
  If actual = 99.5% over 30 days:
  Consumption = (1 - 0.995) * 2,592,000 = 12,960 seconds (3.6 hours)
  Budget Remaining = 2,592 - 12,960 = -10,368 seconds (Budget exhausted)
```

### Burn Rate Alerts
| Burn Rate | Duration | Action |
|---|---|---|
| > 2x (consuming budget 2x faster) | 1 hour | Warning: Investigate |
| > 6x | 5 minutes | Page: Immediate action |
| > 20x | 30 seconds | Critical: Full incident response |
