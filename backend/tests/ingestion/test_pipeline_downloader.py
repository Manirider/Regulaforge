from __future__ import annotations

from pathlib import Path

import pytest
from regulaforge.ingestion.pipeline.downloader import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_CONCURRENT,
    DEFAULT_TIMEOUT,
    DownloadRequest,
    DownloadResult,
    ParallelDownloader,
)


class TestDownloadRequest:
    def test_default_values(self) -> None:
        req = DownloadRequest(url="https://example.com/doc.pdf", destination=Path("/tmp/doc.pdf"))
        assert req.url == "https://example.com/doc.pdf"
        assert req.hash_algorithm == "sha256"
        assert req.timeout_seconds == DEFAULT_TIMEOUT
        assert req.expected_hash is None
        assert req.headers == {}
        assert req.max_file_size_bytes > 0

    def test_custom_values(self) -> None:
        req = DownloadRequest(
            url="https://example.com/doc.pdf",
            destination=Path("/tmp/doc.pdf"),
            expected_hash="abc123",
            hash_algorithm="sha512",
            headers={"Authorization": "Bearer token"},
            timeout_seconds=60,
            max_file_size_bytes=1024,
        )
        assert req.hash_algorithm == "sha512"
        assert req.expected_hash == "abc123"
        assert req.timeout_seconds == 60
        assert req.max_file_size_bytes == 1024
        assert req.headers["Authorization"] == "Bearer token"


class TestDownloadResult:
    def test_success_result(self) -> None:
        result = DownloadResult(
            url="https://example.com/doc.pdf",
            destination=Path("/tmp/doc.pdf"),
            status_code=200,
            actual_hash="abc123",
            bytes_downloaded=1024,
            success=True,
        )
        assert result.success
        assert result.status_code == 200

    def test_failure_result(self) -> None:
        result = DownloadResult(
            url="https://example.com/doc.pdf",
            destination=Path("/tmp/doc.pdf"),
            status_code=404,
            actual_hash=None,
            bytes_downloaded=0,
            success=False,
            error="HTTP 404",
        )
        assert not result.success
        assert result.error == "HTTP 404"


class TestParallelDownloader:
    def test_constructor_defaults(self) -> None:
        downloader = ParallelDownloader()
        assert downloader is not None
        assert downloader._retry_config.max_retries == DEFAULT_MAX_CONCURRENT

    def test_constructor_custom(self) -> None:
        downloader = ParallelDownloader(max_concurrent=10)
        assert downloader is not None

    @pytest.mark.asyncio
    async def test_close_session(self) -> None:
        downloader = ParallelDownloader(max_concurrent=2)
        await downloader.close()
