"""Continuous risk monitoring and alert management.

Implements threshold checking, alert lifecycle management,
and the continuous monitoring loop used by the RegulationMonitorAgent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings
from regulaforge.risk_engine.domain.models import RiskAlert, RiskLevel, RiskScore

logger = get_logger(__name__)


class RiskMonitor:
    """Continuous risk monitoring service.

    Checks risk scores against configurable thresholds, manages
    alert lifecycle (creation, acknowledgment, resolution), and
    supports the continuous monitoring loop called by the
    RegulationMonitorAgent.
    """

    def __init__(
        self,
        alert_repository: Optional[Any] = None,
        event_publisher: Optional[Any] = None,
    ) -> None:
        self._alert_repo = alert_repository
        self._event_publisher = event_publisher
        logger.debug("RiskMonitor initialized")

    async def check_thresholds(
        self,
        risk_score: RiskScore,
    ) -> list[RiskAlert]:
        """Check a risk score against all configured thresholds.

        Compares the overall score and each category score against
        the thresholds defined in settings. Generates alerts for
        any threshold that is breached.

        Args:
            risk_score: The RiskScore to evaluate.

        Returns:
            A list of RiskAlert objects for breached thresholds.
        """
        alerts: list[RiskAlert] = []
        try:
            thresholds = settings.risk_score_thresholds

            if risk_score.overall_score >= thresholds["critical"]:
                alerts.append(self._create_alert(
                    entity_id=risk_score.entity_id,
                    alert_type="critical_threshold_breach",
                    severity=RiskLevel.CRITICAL,
                    message=(
                        f"Critical risk threshold breached: "
                        f"score {risk_score.overall_score:.1f} >= {thresholds['critical']}"
                    ),
                    details={
                        "current_score": risk_score.overall_score,
                        "threshold": thresholds["critical"],
                        "threshold_level": "critical",
                        "category_scores": risk_score.category_scores,
                    },
                ))

            if risk_score.overall_score >= thresholds["high"]:
                alerts.append(self._create_alert(
                    entity_id=risk_score.entity_id,
                    alert_type="high_threshold_breach",
                    severity=RiskLevel.HIGH,
                    message=(
                        f"High risk threshold breached: "
                        f"score {risk_score.overall_score:.1f} >= {thresholds['high']}"
                    ),
                    details={
                        "current_score": risk_score.overall_score,
                        "threshold": thresholds["high"],
                        "threshold_level": "high",
                        "category_scores": risk_score.category_scores,
                    },
                ))

            for category, cat_score in risk_score.category_scores.items():
                if cat_score >= thresholds["critical"]:
                    alerts.append(self._create_alert(
                        entity_id=risk_score.entity_id,
                        alert_type=f"category_{category}_critical",
                        severity=RiskLevel.CRITICAL,
                        message=(
                            f"Critical risk in category '{category}': "
                            f"score {cat_score:.1f} >= {thresholds['critical']}"
                        ),
                        details={
                            "category": category,
                            "current_score": cat_score,
                            "threshold": thresholds["critical"],
                        },
                    ))

            logger.debug(
                "Threshold check for entity %s: %d alerts generated",
                risk_score.entity_id, len(alerts),
            )

            if alerts and self._event_publisher:
                from regulaforge.risk_engine.domain.events import RiskAlertGenerated
                for alert in alerts:
                    event = RiskAlertGenerated(
                        alert_id=alert.id,
                        entity_id=alert.entity_id,
                        alert_type=alert.alert_type,
                        severity=alert.severity,
                        message=alert.message,
                        details=alert.details,
                    )
                    await self._event_publisher.publish(event)

        except Exception as exc:
            logger.error(
                "Threshold check failed: %s", exc, exc_info=True,
            )

        return alerts

    async def escalate_alert(self, alert: RiskAlert) -> RiskAlert:
        """Escalate an alert to a higher severity level.

        Promotes MEDIUM -> HIGH -> CRITICAL. Updates the alert
        details with escalation metadata.

        Args:
            alert: The alert to escalate.

        Returns:
            The escalated RiskAlert.
        """
        try:
            escalation_map = {
                RiskLevel.NEGLIGIBLE: RiskLevel.LOW,
                RiskLevel.LOW: RiskLevel.MEDIUM,
                RiskLevel.MEDIUM: RiskLevel.HIGH,
                RiskLevel.HIGH: RiskLevel.CRITICAL,
                RiskLevel.CRITICAL: RiskLevel.CRITICAL,
            }

            new_severity = escalation_map.get(
                alert.severity, RiskLevel.CRITICAL
            )
            if new_severity == alert.severity:
                logger.debug(
                    "Alert %s already at maximum severity (%s)",
                    alert.id, alert.severity.value,
                )
                return alert

            alert.severity = new_severity
            alert.details["escalated_at"] = datetime.now(timezone.utc).isoformat()
            alert.details["previous_severity"] = alert.severity.value
            alert.details["escalation_reason"] = "Auto-escalation: unresolved alert"

            if self._event_publisher:
                from regulaforge.risk_engine.domain.events import RiskAlertGenerated
                event = RiskAlertGenerated(
                    alert_id=alert.id,
                    entity_id=alert.entity_id,
                    alert_type=f"escalated_{alert.alert_type}",
                    severity=alert.severity,
                    message=f"Alert escalated to {alert.severity.value}: {alert.message}",
                    details=alert.details,
                )
                await self._event_publisher.publish(event)

            logger.info(
                "Alert %s escalated to %s", alert.id, new_severity.value,
            )
            return alert
        except Exception as exc:
            logger.error(
                "Alert escalation failed for %s: %s",
                alert.id, exc, exc_info=True,
            )
            raise RuntimeError(f"Alert escalation failed: {exc}") from exc

    async def get_active_alerts(
        self,
        entity_id: Optional[UUID] = None,
    ) -> list[RiskAlert]:
        """Get all active (unresolved) alerts.

        Args:
            entity_id: Optional entity UUID to filter alerts.

        Returns:
            A list of active RiskAlert objects.
        """
        if self._alert_repo is None:
            logger.warning("No alert repository configured")
            return []
        try:
            return await self._alert_repo.get_active(entity_id=entity_id)
        except Exception as exc:
            logger.error(
                "Failed to fetch active alerts: %s", exc, exc_info=True
            )
            raise RuntimeError(f"Failed to fetch active alerts: {exc}") from exc

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        user_id: UUID,
    ) -> RiskAlert:
        """Acknowledge an alert, preventing further escalation.

        Args:
            alert_id: The UUID of the alert to acknowledge.
            user_id: The UUID of the user acknowledging.

        Returns:
            The acknowledged RiskAlert.

        Raises:
            ValueError: If the alert is not found or already resolved.
        """
        if self._alert_repo is None:
            raise RuntimeError("No alert repository configured")

        try:
            alert = await self._alert_repo.get_by_id(alert_id)
            if alert is None:
                raise ValueError(f"Alert {alert_id} not found")
            if not alert.is_active:
                raise ValueError(f"Alert {alert_id} is already resolved")

            alert.acknowledge(user_id)

            await self._alert_repo.save(alert)

            logger.info(
                "Alert %s acknowledged by user %s", alert_id, user_id,
            )
            return alert
        except ValueError:
            raise
        except Exception as exc:
            logger.error(
                "Failed to acknowledge alert %s: %s",
                alert_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Failed to acknowledge alert: {exc}") from exc

    async def resolve_alert(
        self,
        alert_id: UUID,
        resolution_notes: Optional[str] = None,
    ) -> RiskAlert:
        """Resolve an alert, marking it as closed.

        Args:
            alert_id: The UUID of the alert to resolve.
            resolution_notes: Optional notes about the resolution.

        Returns:
            The resolved RiskAlert.

        Raises:
            ValueError: If the alert is not found or already resolved.
        """
        if self._alert_repo is None:
            raise RuntimeError("No alert repository configured")

        try:
            alert = await self._alert_repo.get_by_id(alert_id)
            if alert is None:
                raise ValueError(f"Alert {alert_id} not found")
            if not alert.is_active:
                raise ValueError(f"Alert {alert_id} is already resolved")

            alert.resolve()
            if resolution_notes:
                alert.details["resolution_notes"] = resolution_notes

            await self._alert_repo.save(alert)

            logger.info(
                "Alert %s resolved: %s", alert_id, resolution_notes or "no notes",
            )
            return alert
        except ValueError:
            raise
        except Exception as exc:
            logger.error(
                "Failed to resolve alert %s: %s",
                alert_id, exc, exc_info=True,
            )
            raise RuntimeError(f"Failed to resolve alert: {exc}") from exc

    async def get_alert_history(
        self,
        entity_id: UUID,
        days: int = 30,
    ) -> list[RiskAlert]:
        """Get alert history for an entity over a time period.

        Args:
            entity_id: The entity UUID.
            days: Number of days of history to retrieve.

        Returns:
            A list of historical RiskAlert objects.
        """
        if self._alert_repo is None:
            logger.warning("No alert repository configured")
            return []
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            return await self._alert_repo.get_by_entity_since(
                entity_id, since=since,
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch alert history: %s", exc, exc_info=True,
            )
            raise RuntimeError(
                f"Failed to fetch alert history: {exc}"
            ) from exc

    async def monitoring_cycle(
        self,
        risk_scores: list[RiskScore],
    ) -> list[RiskAlert]:
        """Execute one continuous monitoring cycle.

        Called by RegulationMonitorAgent at regular intervals.
        Checks all provided risk scores against thresholds and
        returns any generated alerts.

        Args:
            risk_scores: List of RiskScore objects to evaluate.

        Returns:
            A consolidated list of all alerts generated this cycle.
        """
        all_alerts: list[RiskAlert] = []
        try:
            for score in risk_scores:
                alerts = await self.check_thresholds(score)
                all_alerts.extend(alerts)

                # Auto-escalate unresolved CRITICAL alerts
                for alert in alerts:
                    if alert.severity == RiskLevel.CRITICAL:
                        existing = await self.get_active_alerts(
                            entity_id=score.entity_id,
                        )
                        for existing_alert in existing:
                            if (existing_alert.alert_type == alert.alert_type
                                    and not existing_alert.is_acknowledged):
                                await self.escalate_alert(existing_alert)

            logger.info(
                "Monitoring cycle complete: %d scores checked, %d alerts generated",
                len(risk_scores), len(all_alerts),
            )
            return all_alerts
        except Exception as exc:
            logger.error(
                "Monitoring cycle failed: %s", exc, exc_info=True,
            )
            raise RuntimeError(f"Monitoring cycle failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_alert(
        self,
        entity_id: UUID,
        alert_type: str,
        severity: RiskLevel,
        message: str,
        details: dict[str, Any],
    ) -> RiskAlert:
        return RiskAlert(
            id=uuid4(),
            entity_id=entity_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            details=details,
            triggered_at=datetime.now(timezone.utc),
        )
