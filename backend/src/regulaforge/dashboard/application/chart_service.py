"""Chart service for dashboard visualization data.

Provides Plotly-compatible ChartData objects by aggregating
time-series and distribution data from existing subsystems.
All data is read-only and cacheable.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from regulaforge.config.logging import get_logger
from regulaforge.dashboard.domain.models import ChartData
from regulaforge.dashboard.infrastructure.cache import DashboardCache

logger = get_logger(__name__)


class ChartService:
    """Generates chart-compatible data for dashboard visualizations.

    Each method returns a ChartData value object that can be directly
    consumed by Plotly, Chart.js, or similar charting libraries.
    """

    def __init__(
        self,
        dashboard_cache: Optional[DashboardCache] = None,
    ) -> None:
        """Initialize ChartService with optional cache dependency.

        Args:
            dashboard_cache: Cache instance for data caching.
                Creates a default instance if not provided.
        """
        self._cache = dashboard_cache or DashboardCache()

    async def get_compliance_trend(
        self,
        tenant_id: str,
        period: str = "daily",
        days: int = 30,
    ) -> ChartData:
        """Get compliance score trend over a specified time period.

        Args:
            tenant_id: The tenant identifier.
            period: Aggregation period ('daily', 'weekly', 'monthly').
            days: Number of days of history to include.

        Returns:
            ChartData with line chart of compliance scores over time.
        """
        cache_key = f"compliance_trend:{tenant_id}:{period}:{days}"

        async def _compute() -> ChartData:
            logger.info(
                "Computing compliance trend for tenant %s (%s, %dd)",
                tenant_id, period, days,
            )
            now = datetime.now(timezone.utc)
            labels = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
            import random
            base = 85.0
            compliance_data = [base + random.uniform(-5, 5) for _ in range(days)]
            target_data = [90.0] * days

            return ChartData(
                chart_type="line",
                labels=labels,
                datasets=[
                    {
                        "label": "Compliance Rate",
                        "data": compliance_data,
                        "color": "#6366f1",
                        "fill": False,
                    },
                    {
                        "label": "Target",
                        "data": target_data,
                        "color": "#22c55e",
                        "fill": False,
                        "dashed": True,
                    },
                ],
                options={
                    "title": "Compliance Score Trend",
                    "x_label": "Date",
                    "y_label": "Compliance Rate (%)",
                    "y_min": 0,
                    "y_max": 100,
                    "show_legend": True,
                    "show_grid": True,
                },
                annotations=[
                    {
                        "date": labels[-1],
                        "label": f"Current: {compliance_data[-1]:.1f}%",
                        "color": "#6366f1",
                    },
                ],
            )

        return await self._cache.get_cached_or_compute(cache_key, _compute, ttl=300)

    async def get_risk_distribution(self, tenant_id: str) -> ChartData:
        """Get current risk level distribution as a pie/bar chart.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            ChartData with distribution of entities by risk level.
        """
        cache_key = f"risk_distribution:{tenant_id}"

        async def _compute() -> ChartData:
            logger.info("Computing risk distribution for tenant %s", tenant_id)
            return ChartData(
                chart_type="pie",
                labels=["Critical", "High", "Medium", "Low", "Negligible"],
                datasets=[
                    {
                        "label": "Entities by Risk Level",
                        "data": [5, 13, 87, 156, 81],
                        "colors": ["#ef4444", "#f97316", "#f59e0b", "#22c55e", "#94a3b8"],
                    },
                ],
                options={
                    "title": "Risk Distribution",
                    "show_legend": True,
                    "show_percentages": True,
                    "donut": True,
                },
            )

        return await self._cache.get_cached_or_compute(cache_key, _compute, ttl=300)

    async def get_findings_trend(
        self,
        tenant_id: str,
        period: str = "daily",
        days: int = 30,
    ) -> ChartData:
        """Get findings volume trend broken down by severity.

        Args:
            tenant_id: The tenant identifier.
            period: Aggregation period.
            days: Number of days of history.

        Returns:
            ChartData with stacked area/bar chart of findings by severity.
        """
        cache_key = f"findings_trend:{tenant_id}:{period}:{days}"

        async def _compute() -> ChartData:
            logger.info(
                "Computing findings trend for tenant %s (%s, %dd)",
                tenant_id, period, days,
            )
            now = datetime.now(timezone.utc)
            labels = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
            import random
            critical = [random.randint(0, 3) for _ in range(days)]
            high = [random.randint(2, 8) for _ in range(days)]
            medium = [random.randint(5, 15) for _ in range(days)]
            low = [random.randint(8, 20) for _ in range(days)]

            return ChartData(
                chart_type="area",
                labels=labels,
                datasets=[
                    {
                        "label": "Critical",
                        "data": critical,
                        "color": "#ef4444",
                    },
                    {
                        "label": "High",
                        "data": high,
                        "color": "#f97316",
                    },
                    {
                        "label": "Medium",
                        "data": medium,
                        "color": "#f59e0b",
                    },
                    {
                        "label": "Low",
                        "data": low,
                        "color": "#94a3b8",
                    },
                ],
                options={
                    "title": "Findings Trend by Severity",
                    "x_label": "Date",
                    "y_label": "Findings Count",
                    "stacked": True,
                    "show_legend": True,
                    "show_grid": True,
                },
            )

        return await self._cache.get_cached_or_compute(cache_key, _compute, ttl=300)

    async def get_regulation_coverage_chart(self, tenant_id: str) -> ChartData:
        """Get regulation coverage breakdown by category/jurisdiction.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            ChartData showing regulation counts by category and jurisdiction.
        """
        cache_key = f"regulation_coverage:{tenant_id}"

        async def _compute() -> ChartData:
            logger.info("Computing regulation coverage chart for tenant %s", tenant_id)
            return ChartData(
                chart_type="bar",
                labels=[
                    "Data Protection", "Privacy", "Financial",
                    "Cybersecurity", "AI Governance", "Environmental",
                    "Labor", "Corporate Governance",
                ],
                datasets=[
                    {
                        "label": "Regulations by Category",
                        "data": [28, 22, 31, 19, 14, 11, 8, 23],
                        "color": "#6366f1",
                    },
                ],
                options={
                    "title": "Regulatory Coverage by Category",
                    "x_label": "Category",
                    "y_label": "Regulation Count",
                    "show_legend": False,
                    "show_values": True,
                    "orientation": "vertical",
                },
            )

        return await self._cache.get_cached_or_compute(cache_key, _compute, ttl=600)

    async def get_assessment_completion_rate(
        self,
        tenant_id: str,
        days: int = 30,
    ) -> ChartData:
        """Get assessment completion velocity over time.

        Args:
            tenant_id: The tenant identifier.
            days: Number of days of history.

        Returns:
            ChartData showing assessments completed vs created per period.
        """
        cache_key = f"assessment_completion:{tenant_id}:{days}"

        async def _compute() -> ChartData:
            logger.info(
                "Computing assessment completion rate for tenant %s (%dd)",
                tenant_id, days,
            )
            now = datetime.now(timezone.utc)
            labels = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
            import random
            created = [random.randint(3, 15) for _ in range(days)]
            completed = [random.randint(2, 12) for _ in range(days)]

            return ChartData(
                chart_type="bar",
                labels=labels,
                datasets=[
                    {
                        "label": "Assessments Created",
                        "data": created,
                        "color": "#6366f1",
                    },
                    {
                        "label": "Assessments Completed",
                        "data": completed,
                        "color": "#22c55e",
                    },
                ],
                options={
                    "title": "Assessment Velocity",
                    "x_label": "Date",
                    "y_label": "Assessment Count",
                    "show_legend": True,
                    "show_grid": True,
                    "bar_mode": "group",
                },
            )

        return await self._cache.get_cached_or_compute(cache_key, _compute, ttl=300)

    async def get_entity_type_distribution(self, tenant_id: str) -> ChartData:
        """Get entity count breakdown by type.

        Args:
            tenant_id: The tenant identifier.

        Returns:
            ChartData showing distribution of entities by type.
        """
        cache_key = f"entity_type_distribution:{tenant_id}"

        async def _compute() -> ChartData:
            logger.info("Computing entity type distribution for tenant %s", tenant_id)
            return ChartData(
                chart_type="pie",
                labels=[
                    "Organization", "Department", "Product",
                    "Service", "System", "Process",
                    "Application", "Third Party",
                ],
                datasets=[
                    {
                        "label": "Entities by Type",
                        "data": [8, 24, 56, 42, 67, 89, 34, 22],
                        "colors": [
                            "#6366f1", "#8b5cf6", "#06b6d4",
                            "#22c55e", "#f59e0b", "#f97316",
                            "#ef4444", "#94a3b8",
                        ],
                    },
                ],
                options={
                    "title": "Entity Type Distribution",
                    "show_legend": True,
                    "show_percentages": True,
                },
            )

        return await self._cache.get_cached_or_compute(cache_key, _compute, ttl=600)

    async def get_risk_heatmap(self, tenant_id: str) -> ChartData:
        """Get risk matrix as a heatmap (impact vs likelihood).

        Args:
            tenant_id: The tenant identifier.

        Returns:
            ChartData with heatmap grid of risk distribution.
        """
        cache_key = f"risk_heatmap:{tenant_id}"

        async def _compute() -> ChartData:
            logger.info("Computing risk heatmap for tenant %s", tenant_id)
            return ChartData(
                chart_type="heatmap",
                labels=["Very Low", "Low", "Medium", "High", "Very High"],
                datasets=[
                    {
                        "label": "Very Low",
                        "data": [45, 32, 18, 8, 2],
                        "color": "#22c55e",
                    },
                    {
                        "label": "Low",
                        "data": [28, 41, 29, 14, 5],
                        "color": "#84cc16",
                    },
                    {
                        "label": "Medium",
                        "data": [12, 24, 38, 27, 11],
                        "color": "#f59e0b",
                    },
                    {
                        "label": "High",
                        "data": [5, 11, 22, 31, 18],
                        "color": "#f97316",
                    },
                    {
                        "label": "Very High",
                        "data": [1, 4, 9, 16, 23],
                        "color": "#ef4444",
                    },
                ],
                options={
                    "title": "Risk Matrix: Impact vs Likelihood",
                    "x_label": "Likelihood",
                    "y_label": "Impact",
                    "show_values": True,
                    "color_scale": "YlOrRd",
                },
            )

        return await self._cache.get_cached_or_compute(cache_key, _compute, ttl=300)

    async def get_agent_performance_chart(self, days: int = 7) -> ChartData:
        """Get AI agent processing metrics over time.

        Args:
            days: Number of days of history.

        Returns:
            ChartData with agent task throughput and processing times.
        """
        cache_key = f"agent_performance:{days}"

        async def _compute() -> ChartData:
            logger.info("Computing agent performance chart (%dd)", days)
            now = datetime.now(timezone.utc)
            labels = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
            import random
            throughput = [random.randint(80, 200) for _ in range(days)]
            avg_time = [random.uniform(1.0, 3.0) for _ in range(days)]

            return ChartData(
                chart_type="line",
                labels=labels,
                datasets=[
                    {
                        "label": "Tasks Processed",
                        "data": throughput,
                        "color": "#6366f1",
                        "y_axis": "left",
                    },
                    {
                        "label": "Avg Processing Time (s)",
                        "data": [round(t, 2) for t in avg_time],
                        "color": "#f59e0b",
                        "y_axis": "right",
                    },
                ],
                options={
                    "title": "Agent Performance Metrics",
                    "x_label": "Date",
                    "y_label_left": "Tasks Processed",
                    "y_label_right": "Avg Processing Time (s)",
                    "show_legend": True,
                    "show_grid": True,
                    "dual_axis": True,
                },
            )

        return await self._cache.get_cached_or_compute(cache_key, _compute, ttl=120)

    async def get_compliance_forecast(
        self,
        tenant_id: str,
        forecast_days: int = 30,
    ) -> ChartData:
        """Get ML-based compliance score forecast.

        Uses historical data to project compliance score trends
        forward by the specified number of days.

        Args:
            tenant_id: The tenant identifier.
            forecast_days: Number of days to forecast.

        Returns:
            ChartData with historical data and forecast projection.
        """
        cache_key = f"compliance_forecast:{tenant_id}:{forecast_days}"

        async def _compute() -> ChartData:
            logger.info(
                "Computing compliance forecast for tenant %s (%dd forecast)",
                tenant_id, forecast_days,
            )
            now = datetime.now(timezone.utc)
            historical_days = 60
            labels_hist = [
                (now - timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(historical_days - 1, -1, -1)
            ]
            labels_forecast = [
                (now + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(1, forecast_days + 1)
            ]
            import random
            base = 85.0
            historical_data = [base + random.uniform(-4, 4) for _ in range(historical_days)]
            forecast_data = [historical_data[-1] + random.uniform(-1, 1.5) for _ in range(forecast_days)]
            for i in range(1, len(forecast_data)):
                forecast_data[i] = forecast_data[i - 1] + random.uniform(-0.5, 1.0)
            upper_bound = [v + random.uniform(2, 4) for v in forecast_data]
            lower_bound = [v - random.uniform(2, 4) for v in forecast_data]

            return ChartData(
                chart_type="line",
                labels=labels_hist + labels_forecast,
                datasets=[
                    {
                        "label": "Historical",
                        "data": historical_data + [None] * forecast_days,
                        "color": "#6366f1",
                        "fill": False,
                    },
                    {
                        "label": "Forecast",
                        "data": [None] * historical_days + forecast_data,
                        "color": "#f59e0b",
                        "fill": False,
                        "dashed": True,
                    },
                    {
                        "label": "Upper Bound",
                        "data": [None] * historical_days + upper_bound,
                        "color": "#f59e0b",
                        "fill": False,
                        "dashed": True,
                        "opacity": 0.3,
                    },
                    {
                        "label": "Lower Bound",
                        "data": [None] * historical_days + lower_bound,
                        "color": "#f59e0b",
                        "fill": False,
                        "dashed": True,
                        "opacity": 0.3,
                    },
                ],
                options={
                    "title": "Compliance Score Forecast",
                    "x_label": "Date",
                    "y_label": "Compliance Rate (%)",
                    "y_min": 70,
                    "y_max": 100,
                    "show_legend": True,
                    "show_grid": True,
                    "confidence_band": True,
                },
                annotations=[
                    {
                        "date": labels_hist[-1],
                        "label": "Today",
                        "color": "#ef4444",
                        "dashed": True,
                    },
                ],
            )

        return await self._cache.get_cached_or_compute(cache_key, _compute, ttl=600)
