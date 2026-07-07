"""
In-memory metrics collectors for ingestion pipeline observability.

``IngestionMetrics`` aggregates separate ``CrawlMetricsCollector`` and
``DocumentMetricsCollector`` instances, providing a ``snapshot()``
method for Prometheus / health-endpoint consumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from regulaforge.ingestion.domain.models import CrawlSourceType


@dataclass
class CrawlMetricsCollector:
    crawls_started: int = 0
    crawls_completed: int = 0
    crawls_failed: int = 0
    documents_discovered: int = 0
    documents_downloaded: int = 0
    documents_failed: int = 0
    duplicates_found: int = 0
    bytes_downloaded: int = 0
    total_duration_seconds: float = 0.0
    by_source: dict[str, "CrawlMetricsCollector"] = field(default_factory=dict)

    def merge(self, other: "CrawlMetricsCollector") -> None:
        self.crawls_started += other.crawls_started
        self.crawls_completed += other.crawls_completed
        self.crawls_failed += other.crawls_failed
        self.documents_discovered += other.documents_discovered
        self.documents_downloaded += other.documents_downloaded
        self.documents_failed += other.documents_failed
        self.duplicates_found += other.duplicates_found
        self.bytes_downloaded += other.bytes_downloaded
        self.total_duration_seconds += other.total_duration_seconds

    def snapshot(self) -> dict[str, int | float]:
        return {
            "crawls_started": self.crawls_started,
            "crawls_completed": self.crawls_completed,
            "crawls_failed": self.crawls_failed,
            "documents_discovered": self.documents_discovered,
            "documents_downloaded": self.documents_downloaded,
            "documents_failed": self.documents_failed,
            "duplicates_found": self.duplicates_found,
            "bytes_downloaded": self.bytes_downloaded,
            "total_duration_seconds": self.total_duration_seconds,
        }


@dataclass
class DocumentMetricsCollector:
    total_documents: int = 0
    total_versions: int = 0
    total_duplicates: int = 0
    storage_bytes: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    extraction_errors: int = 0
    hash_verification_failures: int = 0

    def snapshot(self) -> dict[str, int | float]:
        return {
            "total_documents": self.total_documents,
            "total_versions": self.total_versions,
            "total_duplicates": self.total_duplicates,
            "storage_bytes": self.storage_bytes,
            **{f"by_category_{k}": v for k, v in self.by_category.items()},
            **{f"by_source_{k}": v for k, v in self.by_source.items()},
            "extraction_errors": self.extraction_errors,
            "hash_verification_failures": self.hash_verification_failures,
        }


class IngestionMetrics:
    def __init__(self) -> None:
        self.crawl = CrawlMetricsCollector()
        self.document = DocumentMetricsCollector()

    def snapshot(self) -> dict[str, object]:
        return {
            "crawl": self.crawl.snapshot(),
            "document": self.document.snapshot(),
        }

    def reset(self) -> None:
        self.crawl = CrawlMetricsCollector()
        self.document = DocumentMetricsCollector()
