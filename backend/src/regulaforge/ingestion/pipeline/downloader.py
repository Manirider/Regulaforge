"""
Parallel streaming downloader with hash verification.

Uses a semaphore to limit concurrency, streams chunks to disk via aiofiles,
and verifies content integrity against an expected hash (SHA-256 by default).

Each logical download is wrapped in :func:`retry_with_backoff` for resilience
against transient network failures.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import aiofiles
from aiohttp import ClientSession, ClientTimeout, TCPConnector

from regulaforge.ingestion.pipeline.retry import RetryConfig, retry_with_backoff

DEFAULT_CHUNK_SIZE = 8192
DEFAULT_MAX_CONCURRENT = 5
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB


@dataclass
class DownloadRequest:
    """Parameters for a single file download.

    Attributes:
        url: Source URL to download from.
        destination: Local filesystem path for the downloaded file.
        expected_hash: Optional SHA-256 hex string to verify integrity.
        hash_algorithm: Hash algorithm for integrity verification.
        headers: Extra HTTP headers to send with the request.
        timeout_seconds: Total request timeout.
        max_file_size_bytes: Maximum allowed download size (prevents OOM).
    """

    url: str
    destination: Path
    expected_hash: str | None = None
    hash_algorithm: str = "sha256"
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = DEFAULT_TIMEOUT
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE


@dataclass
class DownloadResult:
    """Outcome of a single download attempt.

    Attributes:
        url: The source URL.
        destination: Local path written to (may not exist on failure).
        status_code: HTTP response status code.
        actual_hash: Computed content hash (hex string) or None on failure.
        bytes_downloaded: Number of bytes received.
        success: True if the download completed and passed integrity checks.
        error: Human-readable error description on failure.
    """

    url: str
    destination: Path
    status_code: int
    actual_hash: str | None
    bytes_downloaded: int
    success: bool
    error: str | None = None


ProgressCallback = Callable[[str, int, int], None]
"""Signature: ``callback(url, bytes_downloaded, total_bytes)``."""


class ParallelDownloader:
    """Manages concurrent, integrity-verified downloads from multiple URLs.

    Usage::

        downloader = ParallelDownloader(max_concurrent=10)
        req = DownloadRequest(url="https://...", destination=Path("/tmp/doc.pdf"))
        result = await downloader.download(req)
    """

    def __init__(
        self,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        retry_config: RetryConfig | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._retry_config = retry_config or RetryConfig(
            max_retries=DEFAULT_MAX_CONCURRENT,
            base_delay=1.0,
            max_delay=30.0,
            jitter_factor=0.1,
        )
        self._progress_callback = progress_callback
        self._session: ClientSession | None = None

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            connector = TCPConnector(limit=self._max_concurrent, force_close=False)
            self._session = ClientSession(
                connector=connector,
                timeout=ClientTimeout(total=DEFAULT_TIMEOUT),
            )
        return self._session

    async def close(self) -> None:
        """Close the underlying ``aiohttp.ClientSession``."""
        if self._session is not None:
            await self._session.close()

    async def download(self, request: DownloadRequest) -> DownloadResult:
        """Download a single file with concurrency gating and retry.

        Args:
            request: Download parameters.

        Returns:
            A ``DownloadResult`` describing the outcome.
        """
        async with self._semaphore:
            return await retry_with_backoff(
                self._download_single,
                request,
                retry_config=self._retry_config,
            )

    async def download_many(
        self, requests: list[DownloadRequest]
    ) -> list[DownloadResult]:
        """Download multiple files concurrently.

        Uses :func:`asyncio.gather` with ``return_exceptions=False`` so the
        first failure is raised immediately.  Wrap in a try/except for
        bulk operations where partial results are acceptable.

        Args:
            requests: List of download requests.

        Returns:
            List of results in the same order as *requests*.
        """
        tasks = [self.download(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _download_single(self, request: DownloadRequest) -> DownloadResult:
        request.destination.parent.mkdir(parents=True, exist_ok=True)

        async with self.session.get(
            request.url, headers=request.headers, timeout=ClientTimeout(total=request.timeout_seconds)
        ) as response:
            status_code = response.status
            if status_code != 200:
                return DownloadResult(
                    url=request.url,
                    destination=request.destination,
                    status_code=status_code,
                    actual_hash=None,
                    bytes_downloaded=0,
                    success=False,
                    error=f"HTTP {status_code}",
                )

            hasher = hashlib.new(request.hash_algorithm)
            bytes_downloaded = 0
            chunk_size = DEFAULT_CHUNK_SIZE

            async with aiofiles.open(str(request.destination), "wb") as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    bytes_downloaded += len(chunk)
                    if bytes_downloaded > request.max_file_size_bytes:
                        request.destination.unlink(missing_ok=True)
                        return DownloadResult(
                            url=request.url,
                            destination=request.destination,
                            status_code=status_code,
                            actual_hash=None,
                            bytes_downloaded=bytes_downloaded,
                            success=False,
                            error=f"File exceeds {request.max_file_size_bytes} byte limit",
                        )
                    await f.write(chunk)
                    hasher.update(chunk)
                    if self._progress_callback:
                        self._progress_callback(request.url, bytes_downloaded, 0)

            actual_hash = hasher.hexdigest()

            if request.expected_hash and actual_hash != request.expected_hash:
                request.destination.unlink(missing_ok=True)
                return DownloadResult(
                    url=request.url,
                    destination=request.destination,
                    status_code=status_code,
                    actual_hash=actual_hash,
                    bytes_downloaded=bytes_downloaded,
                    success=False,
                    error=(f"Hash mismatch: expected {request.expected_hash}, got {actual_hash}"),
                )

            return DownloadResult(
                url=request.url,
                destination=request.destination,
                status_code=status_code,
                actual_hash=actual_hash,
                bytes_downloaded=bytes_downloaded,
                success=True,
            )
