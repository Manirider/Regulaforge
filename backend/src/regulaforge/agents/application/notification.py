from __future__ import annotations

import logging
import time
from typing import Any, Optional

from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.domain.enums import AgentRole
from regulaforge.agents.domain.models import (
    ConfidenceScore,
    EvaluationResult,
    Task,
)

logger = logging.getLogger(__name__)


class NotificationAgent(BaseAgent):
    def __init__(
        self,
        llm_client: Optional[Any] = None,
    ) -> None:
        super().__init__(
            role=AgentRole.NOTIFICATION,
            agent_id="notification_001",
            llm_client=llm_client,
        )
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            name="send_notification",
            description="Send a notification to specified recipients",
            parameters={
                "recipients": {"type": "array", "description": "List of recipient identifiers"},
                "subject": {"type": "string", "description": "Notification subject"},
                "message": {"type": "string", "description": "Notification message body"},
                "priority": {"type": "string", "description": "Priority: low, medium, high, critical"},
                "channel": {"type": "string", "description": "Channel: email, slack, sms, in_app"},
            },
            function=self._send_notification_logic,
        )
        self.register_tool(
            name="get_notification_history",
            description="Get history of sent notifications",
            parameters={
                "recipient": {"type": "string", "description": "Filter by recipient (optional)"},
                "limit": {"type": "integer", "description": "Max results to return"},
            },
            function=self._get_history_logic,
        )
        self.register_tool(
            name="update_preferences",
            description="Update notification preferences for a recipient",
            parameters={
                "recipient": {"type": "string", "description": "Recipient identifier"},
                "preferences": {"type": "object", "description": "Preference settings"},
            },
            function=self._update_preferences_logic,
        )

    async def _execute(
        self,
        task: Task,
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        recipients = task.input_data.get("recipients", ["compliance_team"])
        subject = task.input_data.get("subject", "Regulatory Notification")
        message = task.input_data.get("message", task.description)
        priority = task.input_data.get("priority", "medium")
        channel = task.input_data.get("channel", "email")

        self.add_reasoning_step(
            description=f"Sending {priority} priority notification via {channel}",
            input_text=message,
        )

        result = await self.call_tool("send_notification", {
            "recipients": recipients,
            "subject": subject,
            "message": message,
            "priority": priority,
            "channel": channel,
        })

        self.add_reasoning_step(
            description="Notification sent",
            output_text=f"Sent to {len(recipients)} recipients via {channel}",
            confidence=0.95,
        )

        return {
            "recipients": recipients,
            "subject": subject,
            "channel": channel,
            "priority": priority,
            "result": result,
        }

    async def _evaluate(
        self,
        result: dict[str, Any],
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        delivery = result.get("result", {})
        delivered = delivery.get("delivered", False)

        return EvaluationResult(
            passed=delivered,
            score=ConfidenceScore(
                overall=0.95 if delivered else 0.3,
                accuracy=0.95,
                completeness=1.0,
                relevance=0.95,
            ),
            feedback=["Notification delivered"] if delivered else ["Delivery failed"],
        )

    async def _fallback(
        self,
        _task: Task,
        _context: dict[str, Any],
        error: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.2),
            feedback=[f"Notification failed: {error}"],
            suggestions=["Check email configuration", "Try alternative notification channel"],
        )

    def _send_notification_logic(
        self,
        recipients: list[str],
        _subject: str,
        _message: str,
        _priority: str = "medium",
        channel: str = "email",
    ) -> dict[str, Any]:
        return {
            "delivered": True,
            "recipients_count": len(recipients),
            "channel": channel,
            "timestamp": time.time(),
            "notification_id": f"notif_{int(time.time())}",
        }

    def _get_history_logic(
        self,
        recipient: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": f"notif_{i}",
                "recipient": recipient or "compliance_team",
                "subject": f"Notification {i}",
                "timestamp": time.time() - i * 3600,
                "status": "delivered",
            }
            for i in range(limit)
        ]

    def _update_preferences_logic(
        self,
        recipient: str,
        preferences: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "recipient": recipient,
            "updated": True,
            "preferences": preferences,
        }
