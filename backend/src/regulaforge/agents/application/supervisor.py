from __future__ import annotations

import logging
from typing import Any, Optional

from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.domain.enums import (
    AgentRole,
    RoutingDecision,
    TaskPriority,
)
from regulaforge.agents.domain.models import (
    ConfidenceScore,
    EvaluationResult,
    Task,
)

logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        llm_model: str = "gpt-4o",
    ) -> None:
        super().__init__(
            role=AgentRole.SUPERVISOR,
            agent_id="supervisor_001",
            llm_client=llm_client,
            llm_model=llm_model,
        )
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.register_tool(
            name="route_task",
            description="Route a task to the appropriate agent based on its type and content",
            parameters={
                "task_description": {"type": "string", "description": "Description of the task"},
                "task_type": {"type": "string", "description": "Type of task (risk, legal, clause, audit, graph, notification)"},  # noqa: E501
            },
            function=self._route_task_logic,
        )
        self.register_tool(
            name="decompose_task",
            description="Break a complex task into subtasks",
            parameters={
                "task_id": {"type": "string"},
                "description": {"type": "string"},
            },
            function=self._decompose_task_logic,
        )
        self.register_tool(
            name="escalate_task",
            description="Escalate a task to human operators",
            parameters={
                "task_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            function=self._escalate_task_logic,
        )

    async def _execute(
        self,
        task: Task,
        _context: dict[str, Any],
    ) -> RoutingDecision:
        self.add_reasoning_step(
            description="Analyzing task and determining routing",
            input_text=task.description,
        )

        routing = await self._determine_routing(task)

        self.add_reasoning_step(
            description=f"Routing decision: {routing.value}",
            output_text=f"Task {task.id} routed to {routing.value}",
            confidence=0.9,
        )

        self.state.routing_decision = routing
        return routing

    async def _determine_routing(self, task: Task) -> RoutingDecision:
        prompt = f"""Analyze this regulatory compliance task and determine the best agent to handle it:

Task: {task.title}
Description: {task.description}
Priority: {task.priority.value}
Tags: {', '.join(task.tags)}

Available agents:
- knowledge_graph: Query and update the regulatory knowledge graph
- risk_prediction: Assess compliance risks and predict regulatory outcomes
- clause_drafting: Draft and refine legal clauses
- legal: Provide legal analysis and interpretation
- audit: Perform compliance audits and generate audit reports
- notification: Send notifications and alerts
- human_approval: Route to human for approval
- monitoring: Monitor system health and agent performance

Respond with only the agent name (e.g., "risk_prediction") that best fits this task.
"""
        response = await self._llm_generate(prompt, max_tokens=50)
        response = response.strip().lower()

        role_map = {
            "knowledge_graph": RoutingDecision.ROUTE_TO_KNOWLEDGE_GRAPH,
            "risk_prediction": RoutingDecision.ROUTE_TO_RISK_PREDICTION,
            "clause_drafting": RoutingDecision.ROUTE_TO_CLAUSE_DRAFTING,
            "legal": RoutingDecision.ROUTE_TO_LEGAL,
            "audit": RoutingDecision.ROUTE_TO_AUDIT,
            "notification": RoutingDecision.ROUTE_TO_NOTIFICATION,
            "human_approval": RoutingDecision.ROUTE_TO_HUMAN_APPROVAL,
            "monitoring": RoutingDecision.ROUTE_TO_MONITORING,
        }

        for key, decision in role_map.items():
            if key in response:
                return decision

        return RoutingDecision.ROUTE_TO_LEGAL

    async def _evaluate(
        self,
        result: RoutingDecision,
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        if result is None:
            return EvaluationResult(
                passed=False,
                score=ConfidenceScore(overall=0.0),
                feedback=["No routing decision made"],
            )
        return EvaluationResult(
            passed=True,
            score=ConfidenceScore(overall=0.95, accuracy=0.95, completeness=1.0, relevance=0.95),
        )

    async def _fallback(
        self,
        _task: Task,
        _context: dict[str, Any],
        error: str,
    ) -> EvaluationResult:
        logger.warning("Supervisor fallback: routing to legal agent")
        self.state.routing_decision = RoutingDecision.ROUTE_TO_LEGAL
        return EvaluationResult(
            passed=True,
            score=ConfidenceScore(overall=0.5),
            feedback=[f"Fallback routing to legal: {error}"],
        )

    def _route_task_logic(
        self,
        _task_description: str,
        task_type: str,
    ) -> str:
        routing_map = {
            "risk": "risk_prediction",
            "legal": "legal",
            "clause": "clause_drafting",
            "audit": "audit",
            "graph": "knowledge_graph",
            "notification": "notification",
            "monitoring": "monitoring",
        }
        return routing_map.get(task_type, "legal")

    def _decompose_task_logic(
        self,
        _task_id: str,
        description: str,
    ) -> list[dict[str, Any]]:
        return [
            {"title": f"Research: {description}", "priority": TaskPriority.HIGH.value},
            {"title": f"Analyze: {description}", "priority": TaskPriority.MEDIUM.value},
            {"title": f"Report: {description}", "priority": TaskPriority.LOW.value},
        ]

    def _escalate_task_logic(
        self,
        task_id: str,
        reason: str,
    ) -> dict[str, Any]:
        return {"task_id": task_id, "reason": reason, "escalated": True}
