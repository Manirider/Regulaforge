from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional, TypedDict

from regulaforge.agents.application.audit import AuditAgent
from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.application.clause_drafting import ClauseDraftingAgent
from regulaforge.agents.application.human_approval import HumanApprovalAgent
from regulaforge.agents.application.knowledge_graph import KnowledgeGraphAgent
from regulaforge.agents.application.legal import LegalAgent
from regulaforge.agents.application.monitoring import MonitoringAgent
from regulaforge.agents.application.notification import NotificationAgent
from regulaforge.agents.application.risk_prediction import RiskPredictionAgent
from regulaforge.agents.application.supervisor import SupervisorAgent
from regulaforge.agents.domain.enums import (
    AgentRole,
    AgentStatus,
    RoutingDecision,
    TaskStatus,
)
from regulaforge.agents.domain.models import (
    AgentState,
    Task,
)

logger = logging.getLogger(__name__)


class AgentWorkflowState(TypedDict, total=False):
    task: Task
    supervisor_state: Optional[AgentState]
    monitoring_state: Optional[AgentState]
    knowledge_graph_state: Optional[AgentState]
    risk_prediction_state: Optional[AgentState]
    clause_drafting_state: Optional[AgentState]
    legal_state: Optional[AgentState]
    audit_state: Optional[AgentState]
    notification_state: Optional[AgentState]
    human_approval_state: Optional[AgentState]
    routing_decision: Optional[RoutingDecision]
    current_agent: Optional[AgentRole]
    errors: list[str]
    start_time: float
    agent_results: dict[str, Any]


class AgentOrchestrator:
    def __init__(
        self,
        llm_client: Optional[Any] = None,
    ) -> None:
        self.llm_client = llm_client
        self.supervisor = SupervisorAgent(llm_client=llm_client)
        self.monitoring = MonitoringAgent(llm_client=llm_client)
        self.knowledge_graph = KnowledgeGraphAgent(llm_client=llm_client)
        self.risk_prediction = RiskPredictionAgent(llm_client=llm_client)
        self.clause_drafting = ClauseDraftingAgent(llm_client=llm_client)
        self.legal = LegalAgent(llm_client=llm_client)
        self.audit = AuditAgent(llm_client=llm_client)
        self.notification = NotificationAgent(llm_client=llm_client)
        self.human_approval = HumanApprovalAgent(llm_client=llm_client)
        self._agents: dict[AgentRole, BaseAgent] = {
            AgentRole.SUPERVISOR: self.supervisor,
            AgentRole.MONITORING: self.monitoring,
            AgentRole.KNOWLEDGE_GRAPH: self.knowledge_graph,
            AgentRole.RISK_PREDICTION: self.risk_prediction,
            AgentRole.CLAUSE_DRAFTING: self.clause_drafting,
            AgentRole.LEGAL: self.legal,
            AgentRole.AUDIT: self.audit,
            AgentRole.NOTIFICATION: self.notification,
            AgentRole.HUMAN_APPROVAL: self.human_approval,
        }

    async def run_workflow(
        self,
        task: Task,
    ) -> AgentWorkflowState:
        state: AgentWorkflowState = {
            "task": task,
            "supervisor_state": None,
            "monitoring_state": None,
            "knowledge_graph_state": None,
            "risk_prediction_state": None,
            "clause_drafting_state": None,
            "legal_state": None,
            "audit_state": None,
            "notification_state": None,
            "human_approval_state": None,
            "routing_decision": None,
            "current_agent": None,
            "errors": [],
            "start_time": time.time(),
            "agent_results": {},
        }

        logger.info(
            "Starting workflow for task %s: %s",
            task.id, task.title,
        )

        try:
            state = await self._supervisor_node(state)
            state = await self._execute_routing(state)
            state = await self._finalize(state)
        except Exception as exc:
            logger.error("Workflow failed: %s", exc)
            state["errors"].append(f"Workflow error: {exc}")

        return state

    async def _supervisor_node(
        self,
        state: AgentWorkflowState,
    ) -> AgentWorkflowState:
        logger.info("Supervisor node processing task %s", state["task"].id)
        state["current_agent"] = AgentRole.SUPERVISOR

        agent_state = await self.supervisor.run(state["task"])
        state["supervisor_state"] = agent_state
        state["routing_decision"] = agent_state.routing_decision
        state["agent_results"]["supervisor"] = {
            "routing": agent_state.routing_decision.value if agent_state.routing_decision else None,
            "reasoning": [
                {"step": s.step_number, "description": s.description}
                for s in agent_state.reasoning_trace
            ],
        }

        return state

    async def _execute_routing(
        self,
        state: AgentWorkflowState,
    ) -> AgentWorkflowState:
        routing = state.get("routing_decision")

        if routing is None:
            state["errors"].append("No routing decision from supervisor")
            return state

        route_map: dict[RoutingDecision, Callable[[AgentWorkflowState], Awaitable[AgentWorkflowState]]] = {
            RoutingDecision.ROUTE_TO_MONITORING: self._run_monitoring,
            RoutingDecision.ROUTE_TO_KNOWLEDGE_GRAPH: self._run_knowledge_graph,
            RoutingDecision.ROUTE_TO_RISK_PREDICTION: self._run_risk_prediction,
            RoutingDecision.ROUTE_TO_CLAUSE_DRAFTING: self._run_clause_drafting,
            RoutingDecision.ROUTE_TO_LEGAL: self._run_legal,
            RoutingDecision.ROUTE_TO_AUDIT: self._run_audit,
            RoutingDecision.ROUTE_TO_NOTIFICATION: self._run_notification,
            RoutingDecision.ROUTE_TO_HUMAN_APPROVAL: self._run_human_approval,
        }

        handler = route_map.get(routing)
        if handler:
            state = await handler(state)
        elif routing == RoutingDecision.COMPLETE:
            logger.info("Workflow complete (no further routing needed)")
        elif routing == RoutingDecision.ESCALATE:
            state["errors"].append("Task escalated to human operators")
            await self._run_notification(state)
        elif routing == RoutingDecision.FAIL:
            state["errors"].append("Task explicitly failed by supervisor")

        return state

    async def _run_agent(
        self,
        state: AgentWorkflowState,
        agent: BaseAgent,
        role_key: str,
        state_key: str,
    ) -> AgentWorkflowState:
        state["current_agent"] = agent.role

        agent_state = await agent.run(state["task"])
        state[state_key] = agent_state  # type: ignore[literal-required]
        state["agent_results"][role_key] = {
            "status": agent_state.status.value,
            "evaluation": {
                "passed": agent_state.evaluation.passed if agent_state.evaluation else False,
                "confidence": {
                    "overall": agent_state.confidence.overall,
                } if agent_state.confidence else {},
                "feedback": agent_state.evaluation.feedback if agent_state.evaluation else [],
            },
            "reasoning": [
                {"step": s.step_number, "description": s.description, "output": s.output}
                for s in agent_state.reasoning_trace
            ],
            "tool_calls": [
                {"tool": tc.tool_name, "error": tc.error}
                for tc in agent_state.tool_calls
            ],
            "fallback_used": agent_state.fallback_used,
        }

        if agent_state.status == AgentStatus.WAITING_FOR_INPUT:
            logger.info("Agent %s waiting for human input", agent.role.value)

        if agent_state.status == AgentStatus.FAILED:
            state["errors"].append(f"{role_key} agent failed")
            agent.reset_state()

        return state

    async def _run_monitoring(self, state: AgentWorkflowState) -> AgentWorkflowState:
        return await self._run_agent(
            state, self.monitoring, "monitoring", "monitoring_state",
        )

    async def _run_knowledge_graph(self, state: AgentWorkflowState) -> AgentWorkflowState:
        return await self._run_agent(
            state, self.knowledge_graph, "knowledge_graph", "knowledge_graph_state",
        )

    async def _run_risk_prediction(self, state: AgentWorkflowState) -> AgentWorkflowState:
        return await self._run_agent(
            state, self.risk_prediction, "risk_prediction", "risk_prediction_state",
        )

    async def _run_clause_drafting(self, state: AgentWorkflowState) -> AgentWorkflowState:
        return await self._run_agent(
            state, self.clause_drafting, "clause_drafting", "clause_drafting_state",
        )

    async def _run_legal(self, state: AgentWorkflowState) -> AgentWorkflowState:
        return await self._run_agent(
            state, self.legal, "legal", "legal_state",
        )

    async def _run_audit(self, state: AgentWorkflowState) -> AgentWorkflowState:
        return await self._run_agent(
            state, self.audit, "audit", "audit_state",
        )

    async def _run_notification(self, state: AgentWorkflowState) -> AgentWorkflowState:
        return await self._run_agent(
            state, self.notification, "notification", "notification_state",
        )

    async def _run_human_approval(self, state: AgentWorkflowState) -> AgentWorkflowState:
        return await self._run_agent(
            state, self.human_approval, "human_approval", "human_approval_state",
        )

    async def _finalize(
        self,
        state: AgentWorkflowState,
    ) -> AgentWorkflowState:
        elapsed = time.time() - state["start_time"]
        task = state["task"]
        task.completed_at = __import__("datetime").datetime.utcnow()

        if state["errors"]:
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.COMPLETED

        state["task"] = task

        logger.info(
            "Workflow completed for task %s: status=%s, time=%.2fs, errors=%d",
            task.id, task.status.value, elapsed, len(state["errors"]),
        )

        return state

    def resolve_human_approval(
        self,
        request_id: str,
        decision: str,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        return self.human_approval.resolve_approval(request_id, decision, notes)

    def get_agent(self, role: AgentRole) -> BaseAgent:
        return self._agents[role]

    def reset_all(self) -> None:
        for agent in self._agents.values():
            agent.reset_state()
