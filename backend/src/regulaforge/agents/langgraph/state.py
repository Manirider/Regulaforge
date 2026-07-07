from __future__ import annotations

import time
from typing import Any, Optional, TypedDict

from regulaforge.agents.domain.enums import AgentRole, RoutingDecision
from regulaforge.agents.domain.models import AgentState, Task


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
    elapsed_seconds: float


def create_initial_state(task: Task) -> AgentWorkflowState:
    return AgentWorkflowState(
        task=task,
        supervisor_state=None,
        monitoring_state=None,
        knowledge_graph_state=None,
        risk_prediction_state=None,
        clause_drafting_state=None,
        legal_state=None,
        audit_state=None,
        notification_state=None,
        human_approval_state=None,
        routing_decision=None,
        current_agent=None,
        errors=[],
        start_time=time.time(),
        agent_results={},
        elapsed_seconds=0.0,
    )
