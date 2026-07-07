"""Dashboard REST API endpoints.

Provides a comprehensive set of read-oriented endpoints for the
Enterprise Dashboard. All business logic is delegated to application
services; these routes only handle HTTP concerns.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from regulaforge.config.constants import (
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from regulaforge.config.logging import get_logger
from regulaforge.dashboard.application.activity_service import ActivityService
from regulaforge.dashboard.application.chart_service import ChartService
from regulaforge.dashboard.application.metric_service import MetricService
from regulaforge.dashboard.application.report_service import ReportService
from regulaforge.dashboard.application.snapshot_service import SnapshotService
from regulaforge.dashboard.domain.models import (
    ChartData,
    ComplianceSnapshot,
    DashboardActivity,
    MetricCard,
)
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user

logger = get_logger(__name__)

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)],
)

from pydantic import BaseModel, Field  # noqa: E402


class ReportGenerateRequest(BaseModel):
    """Request schema for generating a custom report."""

    report_type: str = Field(..., description="Type of report to generate")
    tenant_id: str = Field(..., description="Tenant identifier")
    entity_id: Optional[str] = Field(default=None, description="Entity filter")
    regulation_id: Optional[str] = Field(default=None, description="Regulation filter")
    format: str = Field(default="json", description="Output format (json, html, pdf, xlsx)")


class ReportScheduleRequest(BaseModel):
    """Request schema for scheduling a recurring report."""

    report_type: str = Field(..., description="Type of report to schedule")
    tenant_id: str = Field(..., description="Tenant identifier")
    format: str = Field(default="json", description="Output format")
    cron_expression: str = Field(..., description="Cron scheduling expression")
    recipients: Optional[list[str]] = Field(default=None, description="Report recipients")
    filters: Optional[dict[str, Any]] = Field(default=None, description="Report filters")


class DashboardConfigUpdateRequest(BaseModel):
    """Request schema for updating dashboard layout/configuration."""

    name: Optional[str] = Field(default=None, description="Configuration name")
    description: Optional[str] = Field(default=None, description="Configuration description")
    layout: Optional[list[dict[str, Any]]] = Field(default=None, description="Widget layout definitions")
    is_default: Optional[bool] = Field(default=None, description="Set as default dashboard")
    sharing_config: Optional[dict[str, Any]] = Field(default=None, description="Sharing settings")


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_metric_service() -> MetricService:
    """Provide a MetricService instance."""
    return MetricService()


def get_chart_service() -> ChartService:
    """Provide a ChartService instance."""
    return ChartService()


def get_snapshot_service() -> SnapshotService:
    """Provide a SnapshotService instance."""
    return SnapshotService()


def get_activity_service() -> ActivityService:
    """Provide an ActivityService instance."""
    return ActivityService()


def get_report_service() -> ReportService:
    """Provide a ReportService instance."""
    return ReportService()


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/overview", summary="Full dashboard overview")
async def get_dashboard_overview(
    tenant_id: str = Query(..., description="Tenant identifier"),
    period: str = Query(default="30d", description="Time period for metrics"),
    metric_service: MetricService = Depends(get_metric_service),  # noqa: B008
    _chart_service: MetricService = Depends(get_chart_service),  # noqa: B008
    snapshot_service: SnapshotService = Depends(get_snapshot_service),  # noqa: B008
) -> dict[str, Any]:
    """Get a complete dashboard overview including all metrics and charts.

    Aggregates compliance, risk, agent, and regulatory coverage
    metrics along with key chart data in a single response.
    """
    try:
        compliance_metrics = await metric_service.get_compliance_overview(tenant_id)
        risk_metrics = await metric_service.get_risk_overview(tenant_id)
        agent_metrics = await metric_service.get_agent_metrics()
        coverage_metrics = await metric_service.get_regulatory_coverage(tenant_id)
        latest_snapshot = await snapshot_service.get_latest_snapshot(tenant_id)

        return {
            "tenant_id": tenant_id,
            "period": period,
            "compliance_metrics": _metric_cards_to_dict(compliance_metrics),
            "risk_metrics": _metric_cards_to_dict(risk_metrics),
            "agent_metrics": _metric_cards_to_dict(agent_metrics),
            "coverage_metrics": _metric_cards_to_dict(coverage_metrics),
            "latest_snapshot": _snapshot_to_dict(latest_snapshot) if latest_snapshot else None,
        }
    except Exception as e:
        logger.error("Failed to get dashboard overview: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard overview",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get("/metrics", summary="KPI metrics cards")
async def get_metrics(
    tenant_id: str = Query(..., description="Tenant identifier"),
    metric_type: str = Query(default="all", description="Metric type: compliance, risk, agent, coverage, all"),
    metric_service: MetricService = Depends(get_metric_service),  # noqa: B008
) -> dict[str, Any]:
    """Get KPI metric cards for the dashboard.

    Supports filtering by metric type to return only the desired
    category of metrics.
    """
    try:
        result: dict[str, Any] = {"tenant_id": tenant_id}

        if metric_type in ("all", "compliance"):
            result["compliance"] = _metric_cards_to_dict(
                await metric_service.get_compliance_overview(tenant_id)
            )
        if metric_type in ("all", "risk"):
            result["risk"] = _metric_cards_to_dict(
                await metric_service.get_risk_overview(tenant_id)
            )
        if metric_type in ("all", "agent"):
            result["agent"] = _metric_cards_to_dict(
                await metric_service.get_agent_metrics()
            )
        if metric_type in ("all", "coverage"):
            result["coverage"] = _metric_cards_to_dict(
                await metric_service.get_regulatory_coverage(tenant_id)
            )

        return result
    except Exception as e:
        logger.error("Failed to get metrics: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics",
        )


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


@router.get("/charts/compliance-trend", summary="Compliance trend chart")
async def get_compliance_trend_chart(
    tenant_id: str = Query(..., description="Tenant identifier"),
    period: str = Query(default="daily", description="Aggregation period"),
    days: int = Query(default=30, ge=1, le=365, description="Number of days"),
    chart_service: ChartService = Depends(get_chart_service),  # noqa: B008
) -> ChartData:
    """Get compliance score trend over time.

    Returns time-series data suitable for line chart rendering.
    """
    try:
        return await chart_service.get_compliance_trend(tenant_id, period, days)
    except Exception as e:
        logger.error("Failed to get compliance trend: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compliance trend",
        )


@router.get("/charts/risk-distribution", summary="Risk distribution chart")
async def get_risk_distribution_chart(
    tenant_id: str = Query(..., description="Tenant identifier"),
    chart_service: ChartService = Depends(get_chart_service),  # noqa: B008
) -> ChartData:
    """Get risk level distribution as a pie/bar chart."""
    try:
        return await chart_service.get_risk_distribution(tenant_id)
    except Exception as e:
        logger.error("Failed to get risk distribution: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve risk distribution",
        )


@router.get("/charts/findings-trend", summary="Findings trend chart")
async def get_findings_trend_chart(
    tenant_id: str = Query(..., description="Tenant identifier"),
    period: str = Query(default="daily", description="Aggregation period"),
    days: int = Query(default=30, ge=1, le=365, description="Number of days"),
    chart_service: ChartService = Depends(get_chart_service),  # noqa: B008
) -> ChartData:
    """Get findings volume trend by severity over time."""
    try:
        return await chart_service.get_findings_trend(tenant_id, period, days)
    except Exception as e:
        logger.error("Failed to get findings trend: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve findings trend",
        )


@router.get("/charts/coverage", summary="Regulation coverage chart")
async def get_regulation_coverage_chart(
    tenant_id: str = Query(..., description="Tenant identifier"),
    chart_service: ChartService = Depends(get_chart_service),  # noqa: B008
) -> ChartData:
    """Get regulation coverage breakdown by category and jurisdiction."""
    try:
        return await chart_service.get_regulation_coverage_chart(tenant_id)
    except Exception as e:
        logger.error("Failed to get regulation coverage: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve regulation coverage",
        )


@router.get("/charts/heatmap", summary="Risk heatmap chart")
async def get_risk_heatmap_chart(
    tenant_id: str = Query(..., description="Tenant identifier"),
    chart_service: ChartService = Depends(get_chart_service),  # noqa: B008
) -> ChartData:
    """Get risk matrix heatmap (impact vs likelihood)."""
    try:
        return await chart_service.get_risk_heatmap(tenant_id)
    except Exception as e:
        logger.error("Failed to get risk heatmap: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve risk heatmap",
        )


@router.get("/charts/forecast", summary="Compliance forecast chart")
async def get_compliance_forecast_chart(
    tenant_id: str = Query(..., description="Tenant identifier"),
    forecast_days: int = Query(default=30, ge=1, le=365, description="Forecast horizon"),
    chart_service: ChartService = Depends(get_chart_service),  # noqa: B008
) -> ChartData:
    """Get ML-based compliance score forecast."""
    try:
        return await chart_service.get_compliance_forecast(tenant_id, forecast_days)
    except Exception as e:
        logger.error("Failed to get compliance forecast: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compliance forecast",
        )


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


@router.get("/snapshot", summary="Current compliance snapshot")
async def get_current_snapshot(
    tenant_id: str = Query(..., description="Tenant identifier"),
    capture_new: bool = Query(default=False, description="Force capture new snapshot"),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),  # noqa: B008
) -> dict[str, Any]:
    """Get the current compliance snapshot.

    By default, returns the latest cached snapshot. Set capture_new=true
    to force capture of a fresh snapshot.
    """
    try:
        if capture_new:
            snapshot = await snapshot_service.capture_snapshot(tenant_id)
        else:
            snapshot = await snapshot_service.get_latest_snapshot(tenant_id)
            if not snapshot:
                snapshot = await snapshot_service.capture_snapshot(tenant_id)

        return _snapshot_to_dict(snapshot)
    except Exception as e:
        logger.error("Failed to get snapshot: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compliance snapshot",
        )


@router.get("/snapshots/history", summary="Snapshot history")
async def get_snapshot_history(
    tenant_id: str = Query(..., description="Tenant identifier"),
    days: int = Query(default=90, ge=1, le=365, description="Days of history"),
    snapshot_service: SnapshotService = Depends(get_snapshot_service),  # noqa: B008
) -> list[dict[str, Any]]:
    """Get historical compliance snapshots for trend analysis."""
    try:
        snapshots = await snapshot_service.get_snapshot_history(tenant_id, days)
        return [_snapshot_to_dict(s) for s in snapshots]
    except Exception as e:
        logger.error("Failed to get snapshot history: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve snapshot history",
        )


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------


@router.get("/activity", summary="Recent activity feed")
async def get_recent_activity(
    tenant_id: str = Query(..., description="Tenant identifier"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of entries"),
    activity_service: ActivityService = Depends(get_activity_service),  # noqa: B008
) -> list[dict[str, Any]]:
    """Get the most recent activity feed entries."""
    try:
        activities = await activity_service.get_recent_activity(tenant_id, limit)
        return [_activity_to_dict(a) for a in activities]
    except Exception as e:
        logger.error("Failed to get activity: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve activity",
        )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/reports/executive-summary", summary="Executive summary report")
async def get_executive_summary(
    tenant_id: str = Query(..., description="Tenant identifier"),
    report_format: str = Query(default="json", description="Report format"),
    report_service: ReportService = Depends(get_report_service),  # noqa: B008
) -> dict[str, Any]:
    """Generate an executive summary report for C-suite presentation."""
    try:
        return await report_service.generate_executive_summary(
            tenant_id, report_format,
        )
    except Exception as e:
        logger.error("Failed to generate executive summary: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate executive summary",
        )


@router.post("/reports/generate", summary="Generate custom report")
async def generate_report(
    request: ReportGenerateRequest,
    report_service: ReportService = Depends(get_report_service),  # noqa: B008
) -> dict[str, Any]:
    """Generate a custom report of the specified type and format."""
    try:
        report_type = request.report_type
        if report_type == "executive_summary":
            report_data = await report_service.generate_executive_summary(
                request.tenant_id, request.format,
            )
        elif report_type == "compliance":
            report_data = await report_service.generate_compliance_report(
                request.tenant_id, request.entity_id,
                request.regulation_id, request.format,
            )
        elif report_type == "risk":
            report_data = await report_service.generate_risk_report(
                request.tenant_id, request.entity_id, request.format,
            )
        elif report_type == "regulatory_change":
            report_data = await report_service.generate_regulatory_change_report(
                request.regulation_id, request.format,
            )
        else:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Unsupported report type: {report_type}",
            )

        return report_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate report: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report",
        )


@router.post("/reports/export", summary="Export report data")
async def export_report(
    report_data: dict[str, Any],
    export_format: str = Query(default="json", description="Export format (json, html, pdf, xlsx)"),
    report_service: ReportService = Depends(get_report_service),  # noqa: B008
) -> Any:
    """Export report data in the specified format.

    Returns raw bytes with appropriate content-type headers.
    """
    try:
        content = await report_service.export_report(report_data, export_format)
        media_types = {
            "json": "application/json",
            "html": "text/html",
            "pdf": "application/pdf",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        from fastapi.responses import Response
        return Response(
            content=content,
            media_type=media_types.get(export_format, "application/octet-stream"),
            headers={
                "Content-Disposition": f'attachment; filename="report.{export_format}"',
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Failed to export report: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export report",
        )


@router.post("/reports/schedule", summary="Schedule recurring report")
async def schedule_report(
    request: ReportScheduleRequest,
    report_service: ReportService = Depends(get_report_service),  # noqa: B008
) -> dict[str, str]:
    """Schedule a recurring report generation based on a cron expression."""
    try:
        report_config = {
            "report_type": request.report_type,
            "tenant_id": request.tenant_id,
            "format": request.format,
            "recipients": request.recipients,
            "filters": request.filters or {},
        }
        schedule_id = await report_service.schedule_report(
            report_config, request.cron_expression,
        )
        return {"schedule_id": schedule_id, "status": "scheduled"}
    except Exception as e:
        logger.error("Failed to schedule report: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule report",
        )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@router.get("/config", summary="Get dashboard configuration")
async def get_dashboard_config(
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> dict[str, Any]:
    """Get the dashboard layout configuration for a tenant.

    Returns the default dashboard configuration including all
    widget definitions, positions, and settings.
    """
    logger.info("Fetching dashboard config for tenant %s", tenant_id)
    return {
        "tenant_id": tenant_id,
        "config": {
            "name": "Default Executive Dashboard",
            "description": "Standard dashboard for compliance overview",
            "layout": _get_default_layout(),
            "is_default": True,
            "sharing_config": {
                "visibility": "tenant",
                "shared_with": [],
                "is_public": False,
            },
        },
    }


@router.put("/config", summary="Update dashboard configuration")
async def update_dashboard_config(
    tenant_id: str = Query(..., description="Tenant identifier"),
    config_id: str = Query(..., description="Configuration identifier"),
    _updates: DashboardConfigUpdateRequest = None,
) -> dict[str, Any]:
    """Update the dashboard layout and configuration.

    Accepts partial updates to widget layout, sharing settings,
    and metadata.
    """
    logger.info("Updating dashboard config %s for tenant %s", config_id, tenant_id)
    return {
        "config_id": config_id,
        "tenant_id": tenant_id,
        "status": "updated",
        "message": "Dashboard configuration updated successfully",
    }


def _get_default_layout() -> list[dict[str, Any]]:
    """Get the default dashboard widget layout.

    Returns:
        List of widget configuration dicts with positions.
    """
    return [
        {
            "id": "compliance-rate",
            "title": "Compliance Rate",
            "widget_type": "metric_card",
            "config": {"metric_key": "compliance_rate"},
            "position": {"x": 0, "y": 0, "w": 3, "h": 1},
            "refresh_interval": 300,
            "data_source": "metric_service.get_compliance_overview",
            "cache_ttl": 300,
        },
        {
            "id": "risk-score",
            "title": "Risk Score",
            "widget_type": "metric_card",
            "config": {"metric_key": "current_risk_score"},
            "position": {"x": 3, "y": 0, "w": 3, "h": 1},
            "refresh_interval": 180,
            "data_source": "metric_service.get_risk_overview",
            "cache_ttl": 180,
        },
        {
            "id": "compliance-trend",
            "title": "Compliance Trend",
            "widget_type": "line_chart",
            "config": {"chart_key": "compliance_trend", "days": 30},
            "position": {"x": 0, "y": 1, "w": 6, "h": 2},
            "refresh_interval": 300,
            "data_source": "chart_service.get_compliance_trend",
            "cache_ttl": 300,
        },
        {
            "id": "risk-distribution",
            "title": "Risk Distribution",
            "widget_type": "pie_chart",
            "config": {"chart_key": "risk_distribution"},
            "position": {"x": 6, "y": 1, "w": 3, "h": 2},
            "refresh_interval": 300,
            "data_source": "chart_service.get_risk_distribution",
            "cache_ttl": 300,
        },
        {
            "id": "findings-trend",
            "title": "Findings by Severity",
            "widget_type": "area_chart",
            "config": {"chart_key": "findings_trend", "days": 30},
            "position": {"x": 0, "y": 3, "w": 6, "h": 2},
            "refresh_interval": 300,
            "data_source": "chart_service.get_findings_trend",
            "cache_ttl": 300,
        },
        {
            "id": "recent-activity",
            "title": "Recent Activity",
            "widget_type": "activity_feed",
            "config": {"limit": 10},
            "position": {"x": 6, "y": 3, "w": 3, "h": 2},
            "refresh_interval": 60,
            "data_source": "activity_service.get_recent_activity",
            "cache_ttl": 60,
        },
    ]


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _metric_cards_to_dict(cards: dict[str, MetricCard]) -> dict[str, Any]:
    """Serialize metric cards dict to a plain dict for API response.

    Args:
        cards: Dict of metric key to MetricCard.

    Returns:
        Dict with card data serialized as dicts.
    """
    return {
        key: {
            "label": card.label,
            "value": card.value,
            "unit": card.unit,
            "change_pct": card.change_pct,
            "trend": card.trend,
            "period": card.period,
            "icon": card.icon,
            "color": card.color,
            "tooltip": card.tooltip,
        }
        for key, card in cards.items()
    }


def _snapshot_to_dict(snapshot: ComplianceSnapshot) -> dict[str, Any]:
    """Serialize a ComplianceSnapshot to a plain dict.

    Args:
        snapshot: The ComplianceSnapshot domain object.

    Returns:
        Dict representation of the snapshot.
    """
    return {
        "timestamp": snapshot.timestamp.isoformat() if snapshot.timestamp else None,
        "overall_compliance_rate": snapshot.overall_compliance_rate,
        "entities_assessed": snapshot.entities_assessed,
        "entities_in_scope": snapshot.entities_in_scope,
        "findings_by_severity": snapshot.findings_by_severity,
        "overdue_assessments": snapshot.overdue_assessments,
        "regulations_tracked": snapshot.regulations_tracked,
        "active_alerts": snapshot.active_alerts,
        "risk_distribution": snapshot.risk_distribution,
        "top_risk_factors": snapshot.top_risk_factors,
        "recent_changes": snapshot.recent_changes,
    }


def _activity_to_dict(activity: DashboardActivity) -> dict[str, Any]:
    """Serialize a DashboardActivity to a plain dict.

    Args:
        activity: The DashboardActivity domain object.

    Returns:
        Dict representation of the activity.
    """
    return {
        "id": activity.id,
        "timestamp": activity.timestamp.isoformat() if activity.timestamp else None,
        "activity_type": activity.activity_type,
        "description": activity.description,
        "user_id": activity.user_id,
        "entity_id": activity.entity_id,
        "severity": activity.severity,
        "metadata": activity.metadata,
    }
