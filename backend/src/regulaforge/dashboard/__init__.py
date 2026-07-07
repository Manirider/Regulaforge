"""Enterprise Dashboard Backend for RegulaForge.

Aggregates data from all subsystems (knowledge graph, risk engine, agents,
assessments, regulations) and provides real-time metrics, insights, and
reports for C-suite executives, compliance officers, and risk teams.
"""

from regulaforge.dashboard.domain.models import (
    ChartData,
    ComplianceSnapshot,
    DashboardActivity,
    DashboardConfig,
    DashboardWidget,
    MetricCard,
    TrendReport,
)

__all__ = [
    "DashboardWidget",
    "DashboardConfig",
    "MetricCard",
    "ChartData",
    "ComplianceSnapshot",
    "TrendReport",
    "DashboardActivity",
]
