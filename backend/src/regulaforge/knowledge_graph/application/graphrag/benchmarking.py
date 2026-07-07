"""Latency and throughput benchmarking for the GraphRAG pipeline.

Provides P50/P90/P99 latency measurement, throughput tracking,
and structured benchmark reports for production monitoring.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LatencyStats:
    """Latency statistics for a benchmark run."""

    p50_ms: float
    p90_ms: float
    p99_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float
    stddev_ms: float
    total_requests: int

    def __repr__(self) -> str:
        return (
            f"LatencyStats(P50={self.p50_ms:.1f} P90={self.p90_ms:.1f} "
            f"P99={self.p99_ms:.1f} mean={self.mean_ms:.1f} n={self.total_requests})"
        )


@dataclass
class BenchmarkResult:
    """Complete benchmark result for a pipeline component."""

    component: str
    latency: LatencyStats
    throughput_qps: float
    error_rate: float
    total_time_ms: float
    raw_latencies_ms: list[float] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    """Aggregated benchmark report across all pipeline stages."""

    pipeline: str
    total_queries: int
    total_time_ms: float
    overall_throughput_qps: float
    stage_results: list[BenchmarkResult] = field(default_factory=list)
    error_count: int = 0


class LatencyBenchmarker:
    """Measures latency and throughput for async pipeline stages.

    Records per-call latency, computes percentiles, and generates
    structured reports for production monitoring.
    """

    def __init__(self, warmup_calls: int = 5) -> None:
        self._warmup = warmup_calls

    async def _warmup_phase(self, fn: Callable, sample_query: str) -> None:
        """Run warmup calls sequentially to prepare caches and JIT."""
        if self._warmup <= 0:
            return
        logger.info("Warmup: running %d call(s)", self._warmup)
        for _ in range(self._warmup):
            try:
                await asyncio.wait_for(fn(sample_query), timeout=30.0)
            except Exception:
                pass

    async def benchmark_stage(
        self,
        name: str,
        fn: Callable,
        *,
        queries: list[str],
        concurrency: int = 1,
        timeout: float = 30.0,
    ) -> BenchmarkResult:
        """Benchmark a pipeline stage with the given queries.

        Args:
            name: Stage name (e.g., 'retrieve', 'rerank', 'compress').
            fn: Async callable that accepts a query string.
            queries: List of query strings to benchmark with.
            concurrency: Number of concurrent executions.
            timeout: Per-query timeout in seconds.

        Returns:
            BenchmarkResult with latency stats and throughput.
        """
        logger.info("Benchmarking '%s' with %d queries (concurrency=%d)", name, len(queries), concurrency)

        if self._warmup > 0 and queries:
            await self._warmup_phase(fn, queries[0])

        latencies: list[float] = []
        errors = 0
        lock = asyncio.Lock()

        async def _run_single(query: str) -> None:
            nonlocal errors
            try:
                start = time.perf_counter()
                await asyncio.wait_for(fn(query), timeout=timeout)
                elapsed = (time.perf_counter() - start) * 1000
                async with lock:
                    latencies.append(elapsed)
            except Exception as e:
                async with lock:
                    errors += 1
                logger.warning("Benchmark '%s' query failed: %s", name, str(e))

        sem = asyncio.Semaphore(concurrency)

        async def _run_limited(query: str) -> None:
            async with sem:
                await _run_single(query)

        start_total = time.perf_counter()
        tasks = [_run_limited(q) for q in queries]
        await asyncio.gather(*tasks)
        total_time = (time.perf_counter() - start_total) * 1000

        if not latencies:
            return BenchmarkResult(
                component=name,
                latency=LatencyStats(
                    p50_ms=0.0, p90_ms=0.0, p99_ms=0.0,
                    mean_ms=0.0, min_ms=0.0, max_ms=0.0,
                    stddev_ms=0.0, total_requests=0,
                ),
                throughput_qps=0.0,
                error_rate=1.0 if errors > 0 else 0.0,
                total_time_ms=total_time,
                raw_latencies_ms=[],
            )

        latencies.sort()
        n = len(latencies)
        mean_latency = sum(latencies) / n
        variance = sum((l - mean_latency) ** 2 for l in latencies) / n

        stats = LatencyStats(
            p50_ms=latencies[int(n * 0.50)],
            p90_ms=latencies[int(n * 0.90)],
            p99_ms=latencies[int(n * 0.99)],
            mean_ms=mean_latency,
            min_ms=latencies[0],
            max_ms=latencies[-1],
            stddev_ms=math.sqrt(variance),
            total_requests=n,
        )

        throughput = (n / total_time) * 1000 if total_time > 0 else 0.0
        error_rate = errors / max(n + errors, 1)

        logger.info(
            "Benchmark '%s': P50=%.1fms P90=%.1fms P99=%.1fms QPS=%.1f errors=%d",
            name, stats.p50_ms, stats.p90_ms, stats.p99_ms, throughput, errors,
        )

        return BenchmarkResult(
            component=name,
            latency=stats,
            throughput_qps=round(throughput, 2),
            error_rate=round(error_rate, 4),
            total_time_ms=round(total_time, 2),
            raw_latencies_ms=[round(l, 2) for l in latencies],
        )

    async def benchmark_pipeline(
        self,
        stages: list[tuple[str, Callable]],
        *,
        queries: list[str],
        concurrency: int = 1,
    ) -> BenchmarkReport:
        """Benchmark a multi-stage pipeline end-to-end.

        Args:
            stages: List of (name, async_callable) tuples.
            queries: Query strings.
            concurrency: Parallelism factor.

        Returns:
            BenchmarkReport with per-stage results.
        """
        stage_results: list[BenchmarkResult] = []

        for name, fn in stages:
            result = await self.benchmark_stage(
                name, fn, queries=queries, concurrency=concurrency,
            )
            stage_results.append(result)

        total_time_ms = sum(r.total_time_ms for r in stage_results)
        total_calls = sum(r.latency.total_requests for r in stage_results)
        total_errors = sum(r.error_rate * r.latency.total_requests for r in stage_results)

        return BenchmarkReport(
            pipeline="graphrag_full",
            total_queries=len(queries),
            total_time_ms=round(total_time_ms, 2),
            overall_throughput_qps=round(
                total_calls / (total_time_ms / 1000) if total_time_ms > 0 else 0.0, 2,
            ),
            stage_results=stage_results,
            error_count=int(total_errors),
        )

    def get_report_text(self, report: BenchmarkReport) -> str:
        """Format a benchmark report as human-readable text."""
        lines = [
            "=" * 60,
            f"  GraphRAG Benchmark Report",
            f"  Pipeline: {report.pipeline}",
            f"  Queries: {report.total_queries} | Errors: {report.error_count}",
            f"  Total Time: {report.total_time_ms:.1f}ms | Throughput: {report.overall_throughput_qps:.1f} QPS",
            "=" * 60,
        ]
        for sr in report.stage_results:
            s = sr.latency
            lines.extend([
                f"\n  Stage: {sr.component}",
                f"    P50: {s.p50_ms:.1f}ms | P90: {s.p90_ms:.1f}ms | P99: {s.p99_ms:.1f}ms",
                f"    Mean: {s.mean_ms:.1f}ms | Min: {s.min_ms:.1f}ms | Max: {s.max_ms:.1f}ms",
                f"    StdDev: {s.stddev_ms:.1f}ms | Throughput: {sr.throughput_qps:.1f} QPS | Error Rate: {sr.error_rate:.2%}",
            ])
        return "\n".join(lines)
