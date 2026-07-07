from __future__ import annotations

import logging
from typing import Literal

from regulaforge.agents.domain.enums import RoutingDecision
from regulaforge.agents.langgraph.state import AgentWorkflowState

logger = logging.getLogger(__name__)

AgentNodeName = Literal[
    "monitoring",
    "knowledge_graph",
    "risk_prediction",
    "clause_drafting",
    "legal",
    "audit",
    "notification",
    "human_approval",
    "finalize",
    "escalate",
    "fail",
]

_ROUTE_MAP: dict[RoutingDecision, str] = {
    RoutingDecision.ROUTE_TO_MONITORING: "monitoring",
    RoutingDecision.ROUTE_TO_KNOWLEDGE_GRAPH: "knowledge_graph",
    RoutingDecision.ROUTE_TO_RISK_PREDICTION: "risk_prediction",
    RoutingDecision.ROUTE_TO_CLAUSE_DRAFTING: "clause_drafting",
    RoutingDecision.ROUTE_TO_LEGAL: "legal",
    RoutingDecision.ROUTE_TO_AUDIT: "audit",
    RoutingDecision.ROUTE_TO_NOTIFICATION: "notification",
    RoutingDecision.ROUTE_TO_HUMAN_APPROVAL: "human_approval",
}


def route_after_supervisor(
    state: AgentWorkflowState,
) -> AgentNodeName:
    routing = state.get("routing_decision")

    if routing is None:
        logger.warning("No routing decision from supervisor; routing to legal as default")
        return "legal"

    mapped = _ROUTE_MAP.get(routing)
    if mapped is not None:
        return mapped  # type: ignore[return-value]

    if routing == RoutingDecision.COMPLETE:
        logger.info("Workflow marked complete by supervisor")
        return "finalize"

    if routing == RoutingDecision.ESCALATE:
        logger.warning("Task escalated to human operators by supervisor")
        return "escalate"

    if routing == RoutingDecision.FAIL:
        logger.error("Task explicitly failed by supervisor")
        return "fail"

    logger.warning("Unknown routing decision %s; routing to legal", routing)
    return "legal"


def route_after_agent(
    state: AgentWorkflowState,
) -> Literal["finalize", "notification"]:
    if state.get("errors"):
        return "notification"
    return "finalize"
