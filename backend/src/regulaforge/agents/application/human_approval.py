from __future__ import annotations

import logging
from typing import Any, Optional

from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.domain.enums import AgentRole, AgentStatus, TaskStatus
from regulaforge.agents.domain.models import (
    ConfidenceScore,
    EvaluationResult,
    Task,
)

logger = logging.getLogger(__name__)


class HumanApprovalAgent(BaseAgent):
    def __init__(
        self,
        llm_client: Optional[Any] = None,
    ) -> None:
        super().__init__(
            role=AgentRole.HUMAN_APPROVAL,
            agent_id="human_approval_001",
            llm_client=llm_client,
        )
        self._pending_approvals: dict[str, dict[str, Any]] = {}
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            name="request_approval",
            description="Send a request for human approval",
            parameters={
                "task_id": {"type": "string", "description": "Task requiring approval"},
                "title": {"type": "string", "description": "Approval request title"},
                "description": {"type": "string", "description": "Detailed description"},
                "options": {"type": "array", "description": "Available decision options"},
                "context": {"type": "object", "description": "Supporting context"},
                "timeout_hours": {"type": "number", "description": "Hours before auto-timeout"},
            },
            function=self._request_approval_logic,
        )
        self.register_tool(
            name="check_approval_status",
            description="Check the status of a pending approval request",
            parameters={
                "request_id": {"type": "string", "description": "Approval request ID"},
            },
            function=self._check_status_logic,
        )
        self.register_tool(
            name="approve",
            description="Approve a pending request programmatically (auto-approve for low-risk items)",
            parameters={
                "request_id": {"type": "string", "description": "Approval request ID"},
                "notes": {"type": "string", "description": "Approval notes"},
            },
            function=self._approve_logic,
        )
        self.register_tool(
            name="reject",
            description="Reject a pending request",
            parameters={
                "request_id": {"type": "string", "description": "Approval request ID"},
                "reason": {"type": "string", "description": "Rejection reason"},
            },
            function=self._reject_logic,
        )

    async def _execute(
        self,
        task: Task,
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        request_title = task.input_data.get("title", task.title)
        request_desc = task.input_data.get("description", task.description)
        options = task.input_data.get("options", ["approve", "reject", "request_changes"])
        timeout = task.input_data.get("timeout_hours", 24)

        self.add_reasoning_step(
            description="Creating human approval request",
            input_text=request_desc,
        )

        approval_request = await self.call_tool("request_approval", {
            "task_id": task.id,
            "title": request_title,
            "description": request_desc,
            "options": options,
            "context": task.input_data.get("context", {}),
            "timeout_hours": timeout,
        })

        request_id = approval_request.get("request_id", task.id)

        self.state.status = AgentStatus.WAITING_FOR_INPUT
        task.status = TaskStatus.WAITING_FOR_HUMAN

        self.add_reasoning_step(
            description="Awaiting human decision",
            output_text=f"Approval request {request_id} sent, awaiting response",
            confidence=0.7,
        )

        return {
            "request_id": request_id,
            "title": request_title,
            "status": "pending",
            "options": options,
            "approval_request": approval_request,
            "waiting_for_human": True,
        }

    async def _evaluate(
        self,
        result: dict[str, Any],
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        return EvaluationResult(
            passed=True,
            score=ConfidenceScore(
                overall=1.0,
                accuracy=1.0,
                completeness=1.0,
                relevance=1.0,
            ),
            feedback=[f"Approval request created: {result.get('request_id', 'unknown')}"],
        )

    async def _fallback(
        self,
        _task: Task,
        _context: dict[str, Any],
        error: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.3),
            feedback=[f"Human approval request failed: {error}"],
            suggestions=["Send approval request via email as fallback"],
        )

    def resolve_approval(
        self,
        request_id: str,
        decision: str,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        if request_id in self._pending_approvals:
            self._pending_approvals[request_id]["decision"] = decision
            self._pending_approvals[request_id]["notes"] = notes
            self._pending_approvals[request_id]["resolved_at"] = __import__("time").time()

            if self._interrupt_event is not None:
                self.resume()

        result = self._pending_approvals.get(request_id, {})
        return {
            "request_id": request_id,
            "decision": decision,
            "resolved": True,
            "result": result,
        }

    def _request_approval_logic(
        self,
        task_id: str,
        title: str,
        description: str,
        options: list[str],
        context: Optional[dict[str, Any]] = None,
        timeout_hours: float = 24,
    ) -> dict[str, Any]:
        request_id = f"approval_{task_id}_{int(__import__('time').time())}"
        self._pending_approvals[request_id] = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "options": options,
            "context": context or {},
            "status": "pending",
            "created_at": __import__("time").time(),
            "timeout_hours": timeout_hours,
        }
        return {
            "request_id": request_id,
            "status": "pending",
            "message": f"Approval request '{title}' sent to human operator",
        }

    def _check_status_logic(
        self,
        request_id: str,
    ) -> dict[str, Any]:
        request = self._pending_approvals.get(request_id, {})
        return {
            "request_id": request_id,
            "status": request.get("status", "unknown"),
            "decision": request.get("decision"),
        }

    def _approve_logic(
        self,
        request_id: str,
        notes: str = "Auto-approved",
    ) -> dict[str, Any]:
        return self.resolve_approval(request_id, "approved", notes)

    def _reject_logic(
        self,
        request_id: str,
        reason: str,
    ) -> dict[str, Any]:
        return self.resolve_approval(request_id, "rejected", reason)
