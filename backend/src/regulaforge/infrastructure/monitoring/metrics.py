"""Prometheus metrics definitions for RegulaForge.

Provides application-level metrics for monitoring
API performance, business operations, and system health.
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# ─── API Metrics ────────────────────────────────────────────────────────

http_requests_total = Counter(
    "regulaforge_http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "regulaforge_http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

active_requests = Gauge(
    "regulaforge_http_active_requests",
    "Number of active HTTP requests",
)

# ─── Business Metrics ───────────────────────────────────────────────────

regulations_total = Counter(
    "regulaforge_regulations_total",
    "Total regulations created",
    labelnames=["category"],
)

assessments_total = Counter(
    "regulaforge_assessments_total",
    "Total compliance assessments",
    labelnames=["status"],
)

findings_total = Counter(
    "regulaforge_findings_total",
    "Total compliance findings",
    labelnames=["risk_level"],
)

entities_total = Gauge(
    "regulaforge_entities_total",
    "Total assessable entities",
    labelnames=["entity_type"],
)

# ─── AI Metrics ─────────────────────────────────────────────────────────

ai_requests_total = Counter(
    "regulaforge_ai_requests_total",
    "Total AI processing requests",
    labelnames=["operation", "provider"],
)

ai_request_duration_seconds = Histogram(
    "regulaforge_ai_request_duration_seconds",
    "AI request duration in seconds",
    labelnames=["operation"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

ai_token_usage = Counter(
    "regulaforge_ai_token_usage_total",
    "Total AI token usage",
    labelnames=["model", "type"],  # usage: prompt, completion
)

ai_hallucination_rate = Gauge(
    "regulaforge_ai_hallucination_rate",
    "Rate of detected AI hallucinations",
    labelnames=["severity"],
)

# ─── Database Metrics ───────────────────────────────────────────────────

db_connection_pool_size = Gauge(
    "regulaforge_db_connection_pool_size",
    "Database connection pool size",
)

db_query_duration_seconds = Histogram(
    "regulaforge_db_query_duration_seconds",
    "Database query duration in seconds",
    labelnames=["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# ─── System Info ────────────────────────────────────────────────────────

app_info = Info(
    "regulaforge_app_info",
    "RegulaForge application information",
)
