"""Abstract base agent for the Multi-Agent AI System.

Provides the foundational contract that all specialized agents
must implement, along with built-in retry logic, health reporting,
inter-agent messaging, and logging infrastructure.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from regulaforge.agents.domain.events import AgentError, AgentHeartbeat
from regulaforge.agents.domain.models import (
    AgentCapability,
    AgentMessage,
    AgentStatus,
    AgentTask,
    AgentType,
)
from regulaforge.agents.domain.repository import AgentTaskRepository
from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.llm_provider import LLMProvider
from regulaforge.config.logging import get_logger


class BaseAgent(ABC):
    """Abstract base for all AI agents in the RegulaForge multi-agent system.

    Every specialized agent (regulation monitor, compliance assessor, etc.)
    must extend this class and implement the abstract execute() method.
    """

    def __init__(
        self,
        agent_type: AgentType,
        task_repository: AgentTaskRepository,
        event_publisher: EventPublisher,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        self._agent_type = agent_type
        self._task_repository = task_repository
        self._event_publisher = event_publisher
        self._llm_provider = llm_provider
        self._config = config or {}
        self._logger = get_logger(self.__class__.__name__)
        self._status = AgentStatus.IDLE
        self._active_tasks: dict[str, AgentTask] = {}
        self._capability = AgentCapability(
            agent_type=agent_type,
            task_types=self._get_supported_task_types(),
            max_concurrent_tasks=self._config.get("max_concurrent_tasks", 5),
            average_latency_ms=self._config.get("average_latency_ms", 1000.0),
            confidence_score=self._config.get("confidence_score", 0.95),
        )

    @property
    def agent_type(self) -> AgentType:
        """The type of this agent."""
        return self._agent_type

    @property
    def logger(self) -> logging.Logger:
        """Logger instance for this agent."""
        return self._logger

    @abstractmethod
    def _get_supported_task_types(self) -> list[str]:
        """Get the list of task types this agent can handle.

        Returns:
            A list of task type strings.
        """

    async def initialize(self) -> None:
        """Set up the agent's resources and state.

        Called once when the agent is first registered with the orchestrator.
        Override to load models, connect to services, etc.
        """
        self._logger.info("Agent %s initialized", self._agent_type.value)

    @abstractmethod
    async def execute(self, task: AgentTask) -> dict[str, Any]:
        """Execute a task and return results.

        This is the primary method every agent must implement.

        Args:
            task: The task to execute with input data.

        Returns:
            A dictionary containing the execution results.

        Raises:
            NotImplementedError: If not overridden by subclass.
        """

    def can_handle(self, task_type: str) -> bool:
        """Check if this agent can handle the given task type.

        Args:
            task_type: The task type string to check.

        Returns:
            True if this agent supports the task type.
        """
        return task_type in self._capability.task_types

    def get_capabilities(self) -> AgentCapability:
        """Get the agent's capability description.

        Returns:
            An AgentCapability value object describing what
            this agent can do and its performance characteristics.
        """
        return self._capability

    async def handle_message(self, message: AgentMessage) -> dict[str, Any]:
        """Handle an inter-agent message.

        Override to implement custom message handling behavior.
        The default implementation logs the message and returns
        an acknowledgment.

        Args:
            message: The incoming agent message.

        Returns:
            A response dictionary.
        """
        self._logger.debug(
            "Received message from %s: type=%s urgent=%s",
            message.source_agent.value,
            message.message_type,
            message.urgent,
        )
        return {
            "status": "acknowledged",
            "message_id": str(message.id),
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

    async def send_message(
        self,
        target_agent: AgentType,
        payload: dict[str, Any],
        message_type: str = "generic",
        urgent: bool = False,
        requires_response: bool = False,
    ) -> AgentMessage:
        """Send a message to another agent.

        Args:
            target_agent: The target agent type.
            payload: The message payload data.
            message_type: The type/category of the message.
            urgent: If True, marks the message as high priority.
            requires_response: If True, the sender expects a response.

        Returns:
            The created AgentMessage.
        """
        message = AgentMessage(
            source_agent=self._agent_type,
            target_agent=target_agent,
            message_type=message_type,
            payload=payload,
            urgent=urgent,
            requires_response=requires_response,
        )
        self._logger.info(
            "Sending message to %s: type=%s urgent=%s",
            target_agent.value,
            message_type,
            urgent,
        )
        return message

    async def report_health(self) -> dict[str, Any]:
        """Report the agent's current health status.

        Publishes an AgentHeartbeat event and returns health
        metrics for the orchestrator.

        Returns:
            A dictionary with health metrics.
        """
        health_data = {
            "agent_type": self._agent_type.value,
            "status": self._status.value,
            "active_tasks": len(self._active_tasks),
            "max_concurrent": self._capability.max_concurrent_tasks,
            "uptime_seconds": 0,
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        }

        await self._event_publisher.publish(
            AgentHeartbeat(
                agent_type=self._agent_type.value,
                status=self._status.value,
                active_tasks=len(self._active_tasks),
            )
        )

        return health_data

    async def _execute_with_retry(
        self,
        task: AgentTask,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> dict[str, Any]:
        """Execute a task with exponential backoff retry logic.

        Args:
            task: The task to execute.
            max_retries: Maximum number of retry attempts.
            backoff_factor: Exponential backoff multiplier.

        Returns:
            The execution result.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                self._logger.debug(
                    "Executing task %s (attempt %d/%d)",
                    task.id,
                    attempt + 1,
                    max_retries + 1,
                )
                result = await self.execute(task)
                return result
            except Exception as exc:
                last_exception = exc
                self._logger.warning(
                    "Task %s failed on attempt %d/%d: %s",
                    task.id,
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )

                if attempt < max_retries:
                    delay = backoff_factor ** attempt
                    self._logger.info("Retrying task %s in %.1fs", task.id, delay)
                    await asyncio.sleep(delay)

        error_msg = str(last_exception) if last_exception else "Unknown error"
        self._logger.error(
            "Task %s failed after %d retries: %s",
            task.id,
            max_retries,
            error_msg,
        )
        raise RuntimeError(f"Task failed after {max_retries} retries: {error_msg}")

    async def _report_error(self, error_message: str, task_id: Optional[str] = None) -> None:
        """Report an agent error to the event bus.

        Args:
            error_message: Description of the error.
            task_id: Optional associated task ID.
        """
        self._logger.error("Agent error: %s (task=%s)", error_message, task_id)
        await self._event_publisher.publish(
            AgentError(
                agent_type=self._agent_type.value,
                error_message=error_message,
                task_id=task_id,
            )
        )
