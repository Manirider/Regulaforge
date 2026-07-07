from __future__ import annotations

import pytest
from regulaforge.ingestion.domain.models import DocumentCategory
from regulaforge.ingestion.infrastructure.crawlers.base_crawler import RetryExhausted
from regulaforge.ingestion.infrastructure.crawlers.irdai_crawler import IRDAICrawler
from regulaforge.ingestion.infrastructure.crawlers.rbi_crawler import RBICrawler
from regulaforge.ingestion.infrastructure.crawlers.sebi_crawler import SEBICrawler


class TestRBICrawler:
    def test_categorize_circular(self) -> None:
        crawler = RBICrawler()
        assert crawler._categorize("Circular on KYC") == DocumentCategory.CIRCULAR

    def test_categorize_master_direction(self) -> None:
        crawler = RBICrawler()
        assert crawler._categorize("Master Direction on Foreign Investment") == DocumentCategory.MASTER_DIRECTION

    def test_categorize_notification(self) -> None:
        crawler = RBICrawler()
        assert crawler._categorize("Notification on CRR") == DocumentCategory.NOTIFICATION

    def test_categorize_guideline(self) -> None:
        crawler = RBICrawler()
        assert crawler._categorize("Guidelines on Asset Reconstruction") == DocumentCategory.GUIDELINE

    def test_categorize_press_release(self) -> None:
        crawler = RBICrawler()
        assert crawler._categorize("Press Release on Monetary Policy") == DocumentCategory.PRESS_RELEASE

    def test_categorize_report(self) -> None:
        crawler = RBICrawler()
        assert crawler._categorize("Annual Report 2024") == DocumentCategory.REPORT

    def test_categorize_amendment(self) -> None:
        crawler = RBICrawler()
        assert crawler._categorize("Amendment to Master Direction") == DocumentCategory.AMENDMENT

    def test_categorize_other(self) -> None:
        crawler = RBICrawler()
        assert crawler._categorize("Some Random Document") == DocumentCategory.OTHER


class TestSEBICrawler:
    def test_categorize_circular(self) -> None:
        crawler = SEBICrawler()
        assert crawler._categorize("Circular on Insider Trading") == DocumentCategory.CIRCULAR

    def test_categorize_report(self) -> None:
        crawler = SEBICrawler()
        assert crawler._categorize("Annual Report 2024") == DocumentCategory.REPORT

    def test_categorize_press_release(self) -> None:
        crawler = SEBICrawler()
        assert crawler._categorize("Press Release on Market Data") == DocumentCategory.PRESS_RELEASE


class TestIRDAICrawler:
    def test_categorize_circular(self) -> None:
        crawler = IRDAICrawler()
        assert crawler._categorize("Circular on Motor Insurance") == DocumentCategory.CIRCULAR

    def test_categorize_guideline(self) -> None:
        crawler = IRDAICrawler()
        assert crawler._categorize("Guidelines on Health Insurance") == DocumentCategory.GUIDELINE

    def test_categorize_notification(self) -> None:
        crawler = IRDAICrawler()
        assert crawler._categorize("Notification on Reinsurance") == DocumentCategory.NOTIFICATION


class TestBaseCrawler:
    def test_retry_exhausted_exception(self) -> None:
        exc = RetryExhausted("Test error")
        assert str(exc) == "Test error"
        assert isinstance(exc, Exception)

    def test_parse_date_valid(self) -> None:
        from regulaforge.ingestion.infrastructure.crawlers.base_crawler import BaseCrawler
        crawler = type("TestCrawler", (BaseCrawler,), {"discover_documents": None, "download_document": None})()
        result = crawler._parse_date("15/01/2024", ["%d/%m/%Y"])
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_multiple_formats(self) -> None:
        from regulaforge.ingestion.infrastructure.crawlers.base_crawler import BaseCrawler
        crawler = type("TestCrawler", (BaseCrawler,), {"discover_documents": None, "download_document": None})()
        result = crawler._parse_date("2024-06-15", ["%d/%m/%Y", "%Y-%m-%d"])
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_parse_date_invalid(self) -> None:
        from regulaforge.ingestion.infrastructure.crawlers.base_crawler import BaseCrawler
        crawler = type("TestCrawler", (BaseCrawler,), {"discover_documents": None, "download_document": None})()
        result = crawler._parse_date("not-a-date", ["%d/%m/%Y"])
        assert result is None
