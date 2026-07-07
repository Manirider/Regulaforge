from __future__ import annotations

import logging
import time
from typing import Any, Optional

from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.domain.enums import AgentRole, AgentStatus
from regulaforge.agents.domain.models import (
    ConfidenceScore,
    EvaluationResult,
    Task,
)

logger = logging.getLogger(__name__)


class MonitoringAgent(BaseAgent):
    def __init__(
        self,
        llm_client: Optional[Any] = None,
    ) -> None:
        super().__init__(
            role=AgentRole.MONITORING,
            agent_id="monitoring_001",
            llm_client=llm_client,
        )
        self._agent_health: dict[str, dict[str, Any]] = {}
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            name="check_agent_health",
            description="Check the health status of a specific agent",
            parameters={
                "agent_id": {"type": "string", "description": "Agent identifier"},
            },
            function=self._check_health_logic,
        )
        self.register_tool(
            name="get_system_metrics",
            description="Get current system performance metrics",
            parameters={},
            function=self._get_metrics_logic,
        )
        self.register_tool(
            name="alert",
            description="Send an alert about a system issue",
            parameters={
                "severity": {"type": "string", "description": "Alert severity: low, medium, high, critical"},
                "message": {"type": "string", "description": "Alert message"},
                "source": {"type": "string", "description": "Source of the alert"},
            },
            function=self._alert_logic,
        )

    async def _execute(
        self,
        task: Task,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        start = time.monotonic()

        self.add_reasoning_step(
            description="Starting monitoring check",
            input_text=task.description,
        )

        agents_to_check = context.get("agents", [])
        health_results = {}

        for agent in agents_to_check:
            if isinstance(agent, dict):
                agent_id = agent.get("agent_id", "unknown")
            else:
                agent_id = getattr(agent, "agent_id", "unknown")

            result = await self.call_tool("check_agent_health", {"agent_id": agent_id})
            health_results[agent_id] = result

        metrics = await self.call_tool("get_system_metrics", {})

        alerts = []
        for agent_id, health in health_results.items():
            if health.get("status") in (AgentStatus.FAILED.value, "degraded"):
                alert = await self.call_tool("alert", {
                    "severity": "high",
                    "message": f"Agent {agent_id} is {health.get('status')}",
                    "source": "monitoring",
                })
                alerts.append(alert)

        duration = (time.monotonic() - start) * 1000
        self.add_reasoning_step(
            description=f"Monitoring check complete: {len(health_results)} agents, {len(alerts)} alerts",
            output_text=f"Systems: {metrics.get('status', 'unknown')}",
            confidence=0.95,
            duration_ms=duration,
        )

        return {
            "health": health_results,
            "metrics": metrics,
            "alerts": alerts,
            "duration_ms": duration,
        }

    async def _evaluate(
        self,
        result: dict[str, Any],
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        alert_count = len(result.get("alerts", []))
        return EvaluationResult(
            passed=alert_count == 0,
            score=ConfidenceScore(
                overall=0.9 if alert_count == 0 else 0.6,
                accuracy=0.95,
                completeness=0.9,
                relevance=0.95,
            ),
            feedback=[f"Found {alert_count} alerts"] if alert_count else ["All agents healthy"],
        )

    async def _fallback(
        self,
        _task: Task,
        _context: dict[str, Any],
        error: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.0, accuracy=0.0),
            feedback=[f"Monitoring failed: {error}"],
        )

    def _check_health_logic(self, agent_id: str) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "status": AgentStatus.IDLE.value,
            "healthy": True,
            "last_active": time.time(),
        }

    def _get_metrics_logic(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "active_agents": 1,
            "queue_length": 0,
            "uptime_seconds": 3600,
        }

    def _alert_logic(
        self,
        severity: str,
        message: str,
        source: str,
    ) -> dict[str, Any]:
        return {
            "severity": severity,
            "message": message,
            "source": source,
            "alert_id": f"alert_{int(time.time())}",
            "timestamp": time.time(),
        }
