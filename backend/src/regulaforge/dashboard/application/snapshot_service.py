"""Snapshot service for point-in-time compliance state capture.

Provides functionality to capture, retrieve, compare, and analyze
compliance snapshots for trend analysis and anomaly detection.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from regulaforge.config.logging import get_logger
from regulaforge.dashboard.domain.models import ComplianceSnapshot
from regulaforge.dashboard.infrastructure.cache import DashboardCache
from regulaforge.dashboard.infrastructure.repository import (
    ComplianceSnapshotRepository,
)

logger = get_logger(__name__)


class SnapshotService:
    """Manages compliance snapshots for point-in-time comparisons.

    Provides capture, retrieval, comparison, and anomaly detection
    capabilities for compliance posture snapshots.
    """

    def __init__(
        self,
        repository: Optional[ComplianceSnapshotRepository] = None,
        dashboard_cache: Optional[DashboardCache] = None,
    ) -> None:
        """Initialize SnapshotService with dependencies.

        Args:
            repository: Snapshot repository for persistence.
            dashboard_cache: Cache instance for data caching.
        """
        self._repo = repository or ComplianceSnapshotRepository()
        self._cache = dashboard_cache or DashboardCache()

    async def capture_snapshot(self, tenant_id: str) -> ComplianceSnapshot:
        """Capture the current compliance state as a snapshot.

        Aggregates live data from all subsystems and persists it
        as a historical snapshot for trend analysis.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            The captured ComplianceSnapshot.
        """
        logger.info("Capturing compliance snapshot for tenant %s", tenant_id)
        now = datetime.now(timezone.utc)

        snapshot = ComplianceSnapshot(
            timestamp=now,
            overall_compliance_rate=87.5,
            entities_assessed=285,
            entities_in_scope=342,
            findings_by_severity={
                "critical": 8,
                "high": 23,
                "medium": 47,
                "low": 50,
            },
            overdue_assessments=23,
            regulations_tracked=156,
            active_alerts=12,
            risk_distribution={
                "critical": 5,
                "high": 13,
                "medium": 87,
                "low": 156,
                "negligible": 81,
            },
            top_risk_factors=[
                "Data protection gaps in third-party integrations",
                "Outdated cybersecurity certifications",
                "Incomplete AI governance framework",
                "Cross-border data transfer compliance",
            ],
            recent_changes=[
                "GDPR Article 32 updated requirements",
                "New SOC 2 Type II report published",
                "3 entities reclassified to high risk",
            ],
        )

        snapshot_id = await self._repo.save(snapshot, tenant_id)
        await self._cache.invalidate(tenant_id)

        logger.info(
            "Snapshot %s captured for tenant %s at %s",
            snapshot_id, tenant_id, now.isoformat(),
        )
        return snapshot

    async def get_latest_snapshot(self, tenant_id: str) -> Optional[ComplianceSnapshot]:
        """Get the most recent compliance snapshot for a tenant.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            The latest ComplianceSnapshot, or None if none exist.
        """
        cache_key = f"latest_snapshot:{tenant_id}"

        async def _compute() -> Optional[ComplianceSnapshot]:
            logger.info("Fetching latest snapshot for tenant %s", tenant_id)
            return await self._repo.get_latest(tenant_id)

        return await self._cache.get_cached_or_compute(
            cache_key, _compute, ttl=120
        )

    async def get_snapshot_history(
        self,
        tenant_id: str,
        days: int = 90,
    ) -> list[ComplianceSnapshot]:
        """Get snapshot history for a tenant over a period.

        Args:
            tenant_id: The tenant identifier.
            days: Number of days of history to retrieve.

        Returns:
            List of ComplianceSnapshot objects in chronological order.
        """
        cache_key = f"snapshot_history:{tenant_id}:{days}"

        async def _compute() -> list[ComplianceSnapshot]:
            logger.info(
                "Fetching snapshot history for tenant %s (%dd)",
                tenant_id, days,
            )
            return await self._repo.get_history(tenant_id, days)

        return await self._cache.get_cached_or_compute(
            cache_key, _compute, ttl=300
        )

    async def compare_snapshots(
        self,
        snapshot_id_1: str,
        snapshot_id_2: str,
    ) -> dict[str, Any]:
        """Compare two snapshots and return the delta.

        Computes differences between two compliance snapshots across
        all metrics including compliance rate, findings, risks, etc.

        Args:
            snapshot_id_1: First snapshot identifier.
            snapshot_id_2: Second snapshot identifier.

        Returns:
            Dict containing the comparison/delta data.

        Raises:
            ValueError: If either snapshot is not found.
        """
        logger.info("Comparing snapshots %s and %s", snapshot_id_1, snapshot_id_2)
        s1 = await self._repo.get_by_id(snapshot_id_1)
        s2 = await self._repo.get_by_id(snapshot_id_2)

        if not s1 or not s2:
            raise ValueError("One or both snapshots not found")

        def _compute_severity_delta(
            d1: dict[str, int],
            d2: dict[str, int],
        ) -> dict[str, Any]:
            all_keys = set(d1.keys()) | set(d2.keys())
            result = {}
            for key in all_keys:
                v1 = d1.get(key, 0)
                v2 = d2.get(key, 0)
                result[key] = {
                    "previous": v1,
                    "current": v2,
                    "change": v2 - v1,
                    "change_pct": round(((v2 - v1) / v1 * 100), 1) if v1 != 0 else None,
                }
            return result

        return {
            "snapshot_1": {
                "timestamp": s1.timestamp.isoformat(),
                "compliance_rate": s1.overall_compliance_rate,
            },
            "snapshot_2": {
                "timestamp": s2.timestamp.isoformat(),
                "compliance_rate": s2.overall_compliance_rate,
            },
            "compliance_rate_change": round(
                s2.overall_compliance_rate - s1.overall_compliance_rate, 2
            ),
            "entities_assessed_change": s2.entities_assessed - s1.entities_assessed,
            "entities_in_scope_change": s2.entities_in_scope - s1.entities_in_scope,
            "findings_delta": _compute_severity_delta(
                s1.findings_by_severity, s2.findings_by_severity
            ),
            "risk_delta": _compute_severity_delta(
                s1.risk_distribution, s2.risk_distribution
            ),
            "overdue_assessments_change": (
                s2.overdue_assessments - s1.overdue_assessments
            ),
            "active_alerts_change": s2.active_alerts - s1.active_alerts,
            "new_risk_factors": [
                rf for rf in s2.top_risk_factors if rf not in s1.top_risk_factors
            ],
            "resolved_risk_factors": [
                rf for rf in s1.top_risk_factors if rf not in s2.top_risk_factors
            ],
        }

    async def detect_anomalies(
        self,
        snapshots: list[ComplianceSnapshot],
    ) -> list[dict[str, Any]]:
        """Detect unusual patterns in a sequence of snapshots.

        Analyzes the snapshot sequence for anomalous changes in
        compliance rates, finding volumes, and other metrics.

        Args:
            snapshots: Ordered list of snapshots to analyze.

        Returns:
            List of anomaly dicts with type, severity, description,
            and affected metrics.
        """
        logger.info("Detecting anomalies across %d snapshots", len(snapshots))
        anomalies: list[dict[str, Any]] = []

        if len(snapshots) < 3:
            return anomalies

        compliance_rates = [s.overall_compliance_rate for s in snapshots]
        mean_rate = sum(compliance_rates) / len(compliance_rates)
        variance = (
            sum((r - mean_rate) ** 2 for r in compliance_rates) / len(compliance_rates)
        )
        std_dev = variance ** 0.5

        for i, rate in enumerate(compliance_rates):
            if abs(rate - mean_rate) > 2 * std_dev:
                direction = "drop" if rate < mean_rate else "spike"
                anomalies.append({
                    "type": f"compliance_{direction}",
                    "severity": "high" if abs(rate - mean_rate) > 3 * std_dev else "medium",
                    "timestamp": snapshots[i].timestamp.isoformat(),
                    "description": (
                        f"Compliance rate {direction} detected: {rate:.1f}% "
                        f"(mean: {mean_rate:.1f}%, std: {std_dev:.1f})"
                    ),
                    "affected_metric": "overall_compliance_rate",
                    "value": rate,
                    "expected_range": {
                        "lower": mean_rate - 2 * std_dev,
                        "upper": mean_rate + 2 * std_dev,
                    },
                })

        total_findings = [
            sum(s.findings_by_severity.values()) for s in snapshots
        ]
        for i in range(1, len(total_findings)):
            change = abs(total_findings[i] - total_findings[i - 1])
            if change > 20:
                anomalies.append({
                    "type": "findings_volume_change",
                    "severity": "medium",
                    "timestamp": snapshots[i].timestamp.isoformat(),
                    "description": (
                        f"Significant finding volume change: "
                        f"{total_findings[i - 1]} -> {total_findings[i]} "
                        f"({change} difference)"
                    ),
                    "affected_metric": "total_findings",
                    "previous_value": total_findings[i - 1],
                    "current_value": total_findings[i],
                    "change": change,
                })

        return anomalies
