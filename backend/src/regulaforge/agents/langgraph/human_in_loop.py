from __future__ import annotations

import logging
from typing import Any

from langgraph.types import interrupt

from regulaforge.agents.application.human_approval import HumanApprovalAgent
from regulaforge.agents.langgraph.state import AgentWorkflowState

logger = logging.getLogger(__name__)


async def human_approval_interrupt(
    state: AgentWorkflowState,
) -> AgentWorkflowState:
    task = state["task"]
    logger.info("Human approval requested for task %s: %s", task.id, task.title)

    decision = interrupt(
        {
            "task_id": task.id,
            "title": task.title,
            "description": task.description,
            "input_data": task.input_data,
            "message": "Human approval is required to proceed",
        }
    )

    approved = decision.get("approved", False)
    notes = decision.get("notes", "")

    approval_state = state.get("human_approval_state")
    if approval_state is not None and hasattr(approval_state, "current_task"):
        current = approval_state.current_task
        if current is not None:
            current.output_data = {
                "approved": approved,
                "notes": notes,
            }

    if not approved:
        state["errors"].append(f"Human rejected task {task.id}: {notes}")

    return state
