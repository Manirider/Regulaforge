"""
Metrics collectors for the ingestion pipeline.

Tracks crawl stats (documents discovered/downloaded/failed, bytes,
duration) and document stats (total/versions/duplicates/storage) with
per-source and per-category breakdowns.
"""

from regulaforge.ingestion.monitoring.metrics import (
    IngestionMetrics,
    CrawlMetricsCollector,
    DocumentMetricsCollector,
)

__all__ = [
    "IngestionMetrics",
    "CrawlMetricsCollector",
    "DocumentMetricsCollector",
]
