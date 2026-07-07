from __future__ import annotations

import datetime
import logging
import time
from typing import Any

from regulaforge.agents.domain.enums import AgentRole, AgentStatus, TaskStatus
from regulaforge.agents.langgraph.state import AgentWorkflowState

logger = logging.getLogger(__name__)

NODE_RUN_TIMEOUT_SECONDS = 300


class AgentNodeError(Exception):
    def __init__(self, agent_name: str, message: str, original_error: Optional[Exception] = None) -> None:
        self.agent_name = agent_name
        self.original_error = original_error
        super().__init__(f"[{agent_name}] {message}")


async def supervisor_node(
    state: AgentWorkflowState,
    agent: Any,
) -> AgentWorkflowState:
    logger.info("Supervisor node processing task %s", state["task"].id)
    state["current_agent"] = AgentRole.SUPERVISOR

    agent_state = await agent.run(state["task"])
    state["supervisor_state"] = agent_state
    state["routing_decision"] = agent_state.routing_decision
    state["agent_results"]["supervisor"] = {
        "routing": agent_state.routing_decision.value if agent_state.routing_decision else None,
        "reasoning": [
            {"step": s.step_number, "description": s.description}
            for s in agent_state.reasoning_trace
        ],
        "status": agent_state.status.value,
        "fallback_used": agent_state.fallback_used,
    }

    if agent_state.status == AgentStatus.FAILED:
        state["errors"].append("supervisor agent failed")

    return state


async def monitoring_node(
    state: AgentWorkflowState,
    agent: Any,
) -> AgentWorkflowState:
    return await _run_agent_node(state, agent, "monitoring", "monitoring_state")


async def knowledge_graph_node(
    state: AgentWorkflowState,
    agent: Any,
) -> AgentWorkflowState:
    return await _run_agent_node(state, agent, "knowledge_graph", "knowledge_graph_state")


async def risk_prediction_node(
    state: AgentWorkflowState,
    agent: Any,
) -> AgentWorkflowState:
    return await _run_agent_node(state, agent, "risk_prediction", "risk_prediction_state")


async def clause_drafting_node(
    state: AgentWorkflowState,
    agent: Any,
) -> AgentWorkflowState:
    return await _run_agent_node(state, agent, "clause_drafting", "clause_drafting_state")


async def legal_node(
    state: AgentWorkflowState,
    agent: Any,
) -> AgentWorkflowState:
    return await _run_agent_node(state, agent, "legal", "legal_state")


async def audit_node(
    state: AgentWorkflowState,
    agent: Any,
) -> AgentWorkflowState:
    return await _run_agent_node(state, agent, "audit", "audit_state")


async def notification_node(
    state: AgentWorkflowState,
    agent: Any,
) -> AgentWorkflowState:
    return await _run_agent_node(state, agent, "notification", "notification_state")


async def human_approval_node(
    state: AgentWorkflowState,
    agent: Any,
) -> AgentWorkflowState:
    return await _run_agent_node(state, agent, "human_approval", "human_approval_state")


async def _run_agent_node(
    state: AgentWorkflowState,
    agent: Any,
    role_key: str,
    state_key: str,
) -> AgentWorkflowState:
    state["current_agent"] = agent.role

    try:
        agent_state = await agent.run(state["task"])
    except Exception as exc:
        state["errors"].append(f"{role_key} agent raised exception: {exc}")
        logger.error("Agent %s run failed: %s", role_key, exc)
        return state

    state[state_key] = agent_state
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


async def finalize_node(state: AgentWorkflowState) -> AgentWorkflowState:
    elapsed = time.time() - state["start_time"]
    state["elapsed_seconds"] = elapsed
    task = state["task"]
    task.completed_at = datetime.datetime.utcnow()

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
