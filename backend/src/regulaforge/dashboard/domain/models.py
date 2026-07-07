"""Domain models and value objects for the Enterprise Dashboard.

These are pure domain data structures representing dashboard widgets,
metric cards, chart data, compliance snapshots, trend reports, and
activity records. All are immutable dataclasses with no business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Union


@dataclass(frozen=True)
class DashboardWidget:
    """Configuration for a single dashboard widget/card.

    Attributes:
        id: Unique widget identifier.
        title: Display title shown on the widget.
        widget_type: Type descriptor (e.g. 'metric_card', 'line_chart').
        config: Widget-specific configuration dict.
        position: Layout position/size dict with keys x, y, w, h.
        refresh_interval: Auto-refresh interval in seconds (0 = no refresh).
        data_source: Backend data source key for this widget.
        last_updated: Timestamp of last data refresh.
        cache_ttl: Cache time-to-live in seconds for this widget's data.
    """

    id: str
    title: str
    widget_type: str
    config: dict[str, Any] = field(default_factory=dict)
    position: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "w": 3, "h": 2})
    refresh_interval: int = 300
    data_source: str = ""
    last_updated: Optional[datetime] = None
    cache_ttl: int = 300


@dataclass(frozen=True)
class DashboardConfig:
    """Complete dashboard layout and configuration for a tenant.

    Attributes:
        id: Unique configuration identifier.
        name: Human-readable configuration name.
        description: Optional description of this dashboard layout.
        layout: Ordered list of DashboardWidget definitions.
        tenant_id: Tenant that owns this configuration.
        created_by: User ID that created this configuration.
        is_default: Whether this is the default dashboard for the tenant.
        sharing_config: Sharing/visibility configuration dict.
    """

    id: str
    name: str
    description: Optional[str] = None
    layout: list[DashboardWidget] = field(default_factory=list)
    tenant_id: str = ""
    created_by: Optional[str] = None
    is_default: bool = False
    sharing_config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricCard:
    """A single KPI metric card value object.

    Attributes:
        label: Human-readable metric name.
        value: Current numeric value of the metric.
        unit: Unit of measurement (e.g. '%', 'count', 'ms').
        change_pct: Percentage change from previous period (None if N/A).
        trend: Direction indicator - 'up', 'down', or 'flat'.
        period: Time period this metric represents (e.g. '24h', '7d', '30d').
        icon: Icon identifier for visual representation.
        color: Color code for visual distinction.
        tooltip: Help text shown on hover.
    """

    label: str
    value: Union[float, int]
    unit: str = ""
    change_pct: Optional[float] = None
    trend: str = "flat"
    period: str = "current"
    icon: str = "chart-bar"
    color: str = "#6366f1"
    tooltip: str = ""


@dataclass(frozen=True)
class ChartData:
    """Chart data value object compatible with Plotly/Chart.js.

    Attributes:
        chart_type: Type of chart ('line', 'bar', 'pie', 'heatmap',
            'area', 'scatter').
        labels: Category labels for the X axis or legend.
        datasets: List of dataset dicts each with label, data, and color.
        options: Chart rendering options (axis labels, legends, etc.).
        annotations: Optional list of annotation dicts for key points.
    """

    chart_type: str = "bar"
    labels: list[str] = field(default_factory=list)
    datasets: list[dict[str, Any]] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    annotations: Optional[list[dict[str, Any]]] = None


@dataclass(frozen=True)
class ComplianceSnapshot:
    """Point-in-time snapshot of compliance posture.

    Attributes:
        timestamp: When this snapshot was captured.
        overall_compliance_rate: Percentage of compliance across all entities.
        entities_assessed: Number of entities that have been assessed.
        entities_in_scope: Total number of entities in scope.
        findings_by_severity: Dict mapping severity level to count.
        overdue_assessments: Number of assessments past due.
        regulations_tracked: Number of regulations being tracked.
        active_alerts: Number of currently active alerts.
        risk_distribution: Dict mapping risk level to count.
        top_risk_factors: List of top risk factor descriptions.
        recent_changes: List of notable recent changes.
    """

    timestamp: datetime
    overall_compliance_rate: float = 0.0
    entities_assessed: int = 0
    entities_in_scope: int = 0
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    overdue_assessments: int = 0
    regulations_tracked: int = 0
    active_alerts: int = 0
    risk_distribution: dict[str, int] = field(default_factory=dict)
    top_risk_factors: list[str] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TrendReport:
    """Time-series trend data for a specific metric.

    Attributes:
        metric_name: Name of the metric being tracked.
        period: Aggregation period ('daily', 'weekly', 'monthly',
            'quarterly', 'yearly').
        data_points: Historical data points as {date, value} dicts.
        trend_line: Predicted/forecasted values as {date, predicted} dicts.
        change_statistics: Statistical summary (mean, std_dev, min, max,
            last_change).
        insights: List of human-readable insight strings.
    """

    metric_name: str
    period: str = "daily"
    data_points: list[dict[str, Any]] = field(default_factory=list)
    trend_line: list[dict[str, Any]] = field(default_factory=list)
    change_statistics: dict[str, Any] = field(default_factory=dict)
    insights: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DashboardActivity:
    """A single activity/event entry in the dashboard activity feed.

    Attributes:
        id: Unique activity identifier.
        timestamp: When the activity occurred.
        activity_type: Type of activity (e.g. 'assessment_completed',
            'alert_triggered').
        description: Human-readable activity description.
        user_id: User who performed the activity.
        entity_id: Related entity identifier (if applicable).
        severity: Severity level ('info', 'warning', 'critical').
        metadata: Additional structured data about the activity.
    """

    id: str
    timestamp: datetime
    activity_type: str
    description: str
    user_id: Optional[str] = None
    entity_id: Optional[str] = None
    severity: str = "info"
    metadata: dict[str, Any] = field(default_factory=dict)
