"""Dashboard overview API endpoint.

Provides a lightweight dashboard endpoint that returns data in the
format expected by the frontend. Returns static demo data until the
full dashboard module is wired to a live database.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends

from regulaforge.config.constants import HTTP_200_OK
from regulaforge.domain.entities.user import User
from regulaforge.infrastructure.monitoring.metrics import (
    assessments_total,
    entities_total,
    findings_total,
    regulations_total,
)
from regulaforge.interfaces.api.middleware.auth_middleware import get_current_user

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/overview", status_code=HTTP_200_OK)
async def get_dashboard_overview(
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """Get dashboard overview data.

    Returns metrics, recent activity, and chart data for the
    frontend dashboard. Currently returns demo data; will be
    replaced with live aggregation when the database is connected.
    """
    now = datetime.now(timezone.utc)

    regulations_total.labels(category="all").inc(156)
    assessments_total.labels(status="completed").inc(89)
    assessments_total.labels(status="in_progress").inc(34)
    findings_total.labels(risk_level="low").inc(12)
    findings_total.labels(risk_level="medium").inc(7)
    findings_total.labels(risk_level="high").inc(3)
    findings_total.labels(risk_level="critical").inc(1)
    entities_total.labels(entity_type="organization").set(12)
    entities_total.labels(entity_type="department").set(24)
    entities_total.labels(entity_type="system").set(8)
    entities_total.labels(entity_type="process").set(4)

    return {
        "metrics": [
            {"id": "1", "label": "Compliance Rate", "value": 94, "previous_value": 91, "change_percentage": 3.3, "trend": "up", "icon": "shield"},  # noqa: E501
            {"id": "2", "label": "Open Findings", "value": 23, "previous_value": 28, "change_percentage": -17.9, "trend": "down", "icon": "alert"},  # noqa: E501
            {"id": "3", "label": "Active Regulations", "value": 156, "previous_value": 148, "change_percentage": 5.4, "trend": "up", "icon": "clipboard"},  # noqa: E501
            {"id": "4", "label": "Entities Monitored", "value": 48, "previous_value": 45, "change_percentage": 6.7, "trend": "up", "icon": "building"},  # noqa: E501
        ],
        "recent_activity": [
            {"id": "1", "type": "regulation", "description": "GDPR update v2.1 published", "user_name": "Admin", "timestamp": _ago(now, 15), "metadata": {}},  # noqa: E501
            {"id": "2", "type": "assessment", "description": "Q4 Compliance Assessment completed", "user_name": "John Doe", "timestamp": _ago(now, 120), "metadata": {}},  # noqa: E501
            {"id": "3", "type": "document", "description": "SOC 2 Report uploaded", "user_name": "Jane Smith", "timestamp": _ago(now, 300), "metadata": {}},  # noqa: E501
            {"id": "4", "type": "user", "description": "New user onboarded: Sarah Wilson", "user_name": "Admin", "timestamp": _ago(now, 1440), "metadata": {}},  # noqa: E501
        ],
        "compliance_rate": 94,
        "open_findings": 23,
        "active_regulations": 156,
        "entities_monitored": 48,
    }


@router.get("/charts/compliance-trend", status_code=HTTP_200_OK)
async def get_compliance_trend(
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[dict[str, Any]]:
    return [
        {"date": "Jan", "compliance": 85, "target": 90},
        {"date": "Feb", "compliance": 87, "target": 90},
        {"date": "Mar", "compliance": 86, "target": 90},
        {"date": "Apr", "compliance": 89, "target": 90},
        {"date": "May", "compliance": 91, "target": 92},
        {"date": "Jun", "compliance": 90, "target": 92},
        {"date": "Jul", "compliance": 92, "target": 92},
        {"date": "Aug", "compliance": 94, "target": 93},
        {"date": "Sep", "compliance": 93, "target": 93},
        {"date": "Oct", "compliance": 95, "target": 94},
        {"date": "Nov", "compliance": 94, "target": 94},
        {"date": "Dec", "compliance": 96, "target": 95},
    ]


@router.get("/charts/risk-distribution", status_code=HTTP_200_OK)
async def get_risk_distribution(
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[dict[str, Any]]:
    return [
        {"name": "Low", "value": 45, "color": "#22c55e"},
        {"name": "Medium", "value": 30, "color": "#eab308"},
        {"name": "High", "value": 18, "color": "#f97316"},
        {"name": "Critical", "value": 7, "color": "#ef4444"},
    ]


@router.get("/charts/findings-trend", status_code=HTTP_200_OK)
async def get_findings_trend(
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[dict[str, Any]]:
    return [
        {"month": "Jul", "open": 12, "closed": 8},
        {"month": "Aug", "open": 15, "closed": 11},
        {"month": "Sep", "open": 10, "closed": 14},
        {"month": "Oct", "open": 8, "closed": 12},
        {"month": "Nov", "open": 6, "closed": 10},
        {"month": "Dec", "open": 9, "closed": 13},
    ]


@router.get("/charts/coverage", status_code=HTTP_200_OK)
async def get_coverage(
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[dict[str, Any]]:
    return [
        {"name": "GDPR", "value": 92, "fill": "#6366f1"},
        {"name": "SOC 2", "value": 88, "fill": "#22c55e"},
        {"name": "ISO 27001", "value": 76, "fill": "#f97316"},
        {"name": "PCI DSS", "value": 95, "fill": "#06b6d4"},
        {"name": "HIPAA", "value": 70, "fill": "#eab308"},
    ]


def _ago(now: datetime, minutes: int) -> str:
    return (now.replace(microsecond=0) - timedelta(minutes=minutes)).isoformat()
