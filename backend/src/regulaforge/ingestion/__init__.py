"""
RegulaForge Regulatory Data Ingestion Module.

A comprehensive, production-grade pipeline for discovering, downloading,
deduplicating, extracting, and storing regulatory documents from Indian
financial authorities (RBI, SEBI, IRDAI).

Architecture follows Clean Architecture / hexagonal pattern:
  - domain: business entities, repository interfaces, events
  - application: orchestrators and use-case services
  - infrastructure: concrete crawlers, extractors, fingerprinting, storage, scheduler
  - interfaces: REST API (FastAPI) and CLI (argparse)
  - pipeline: retry/backoff, download manager, scheduler
  - detectors: fingerprint, duplicate, version, hash verification
  - extractors: PDF and HTML content extraction
  - monitoring: Prometheus-style metrics collectors
  - storage: pluggable storage backends (local, S3)
"""

from regulaforge.ingestion.domain.models import (
    CrawlJob,
    CrawlJobStatus,
    CrawlSourceConfig,
    CrawlSourceType,
    DocumentCategory,
    DocumentFingerprint,
    DocumentStatus,
    RegulatoryDocument,
)
from regulaforge.ingestion.domain.repository import (
    CrawlJobRepository,
    DocumentRepository,
    FingerprintRepository,
)

__all__ = [
    "CrawlJob",
    "CrawlJobStatus",
    "CrawlSourceConfig",
    "CrawlSourceType",
    "DocumentCategory",
    "DocumentFingerprint",
    "DocumentStatus",
    "RegulatoryDocument",
    "CrawlJobRepository",
    "DocumentRepository",
    "FingerprintRepository",
]
