"""Domain events for the Multi-Agent AI System.

Each event captures a meaningful state change in the agent
orchestration lifecycle, enabling event-driven communication
and observability across the system.
"""

from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.events.base import DomainEvent


class TaskCreated(DomainEvent):
    """Emitted when a new task is submitted to the agent system."""

    def __init__(
        self,
        task_id: UUID,
        agent_type: str,
        task_type: str,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.task.created",
            aggregate_id=task_id,
            aggregate_type="agent_task",
            data={
                "agent_type": agent_type,
                "task_type": task_type,
            },
            correlation_id=correlation_id,
        )


class TaskAssigned(DomainEvent):
    """Emitted when a task is assigned to a specific agent."""

    def __init__(
        self,
        task_id: UUID,
        agent_type: str,
        handler_name: str,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.task.assigned",
            aggregate_id=task_id,
            aggregate_type="agent_task",
            data={
                "agent_type": agent_type,
                "handler": handler_name,
            },
            correlation_id=correlation_id,
        )


class TaskCompleted(DomainEvent):
    """Emitted when a task completes successfully."""

    def __init__(
        self,
        task_id: UUID,
        agent_type: str,
        task_type: str,
        output_summary: str,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.task.completed",
            aggregate_id=task_id,
            aggregate_type="agent_task",
            data={
                "agent_type": agent_type,
                "task_type": task_type,
                "output_summary": output_summary,
            },
            correlation_id=correlation_id,
        )


class TaskFailed(DomainEvent):
    """Emitted when a task fails after exhausting retries."""

    def __init__(
        self,
        task_id: UUID,
        agent_type: str,
        task_type: str,
        error_message: str,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.task.failed",
            aggregate_id=task_id,
            aggregate_type="agent_task",
            data={
                "agent_type": agent_type,
                "task_type": task_type,
                "error": error_message,
            },
            correlation_id=correlation_id,
        )


class TaskRetrying(DomainEvent):
    """Emitted when a failed task is scheduled for retry."""

    def __init__(
        self,
        task_id: UUID,
        agent_type: str,
        attempt: int,
        max_retries: int,
        error_message: str,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.task.retrying",
            aggregate_id=task_id,
            aggregate_type="agent_task",
            data={
                "agent_type": agent_type,
                "attempt": attempt,
                "max_retries": max_retries,
                "error": error_message,
            },
            correlation_id=correlation_id,
        )


class WorkflowStarted(DomainEvent):
    """Emitted when a workflow execution begins."""

    def __init__(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        workflow_name: str,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.workflow.started",
            aggregate_id=execution_id,
            aggregate_type="workflow_execution",
            data={
                "workflow_id": str(workflow_id),
                "workflow_name": workflow_name,
            },
            correlation_id=correlation_id,
        )


class WorkflowStepCompleted(DomainEvent):
    """Emitted when an individual step within a workflow completes."""

    def __init__(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        step_order: int,
        agent_type: str,
        task_id: UUID,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.workflow.step_completed",
            aggregate_id=execution_id,
            aggregate_type="workflow_execution",
            data={
                "workflow_id": str(workflow_id),
                "step_order": step_order,
                "agent_type": agent_type,
                "task_id": str(task_id),
            },
            correlation_id=correlation_id,
        )


class WorkflowCompleted(DomainEvent):
    """Emitted when all steps in a workflow have completed."""

    def __init__(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        step_count: int,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.workflow.completed",
            aggregate_id=execution_id,
            aggregate_type="workflow_execution",
            data={
                "workflow_id": str(workflow_id),
                "step_count": step_count,
            },
            correlation_id=correlation_id,
        )


class WorkflowFailed(DomainEvent):
    """Emitted when a workflow fails due to a step failure."""

    def __init__(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        failed_step: int,
        error_message: str,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.workflow.failed",
            aggregate_id=execution_id,
            aggregate_type="workflow_execution",
            data={
                "workflow_id": str(workflow_id),
                "failed_step": failed_step,
                "error": error_message,
            },
            correlation_id=correlation_id,
        )


class AgentHeartbeat(DomainEvent):
    """Emitted periodically by agents to report liveness."""

    def __init__(
        self,
        agent_type: str,
        status: str,
        active_tasks: int,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.heartbeat",
            aggregate_id=UUID(int=0),
            aggregate_type=f"agent_{agent_type}",
            data={
                "agent_type": agent_type,
                "status": status,
                "active_tasks": active_tasks,
            },
            correlation_id=correlation_id,
        )


class AgentError(DomainEvent):
    """Emitted when an agent encounters an internal error."""

    def __init__(
        self,
        agent_type: str,
        error_message: str,
        task_id: Optional[UUID] = None,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.error",
            aggregate_id=UUID(int=0),
            aggregate_type=f"agent_{agent_type}",
            data={
                "agent_type": agent_type,
                "error": error_message,
                "task_id": str(task_id) if task_id else None,
            },
            correlation_id=correlation_id,
        )


class AgentOverloaded(DomainEvent):
    """Emitted when an agent exceeds its capacity threshold."""

    def __init__(
        self,
        agent_type: str,
        current_tasks: int,
        max_concurrent: int,
        correlation_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="agent.overloaded",
            aggregate_id=UUID(int=0),
            aggregate_type=f"agent_{agent_type}",
            data={
                "agent_type": agent_type,
                "current_tasks": current_tasks,
                "max_concurrent": max_concurrent,
            },
            correlation_id=correlation_id,
        )
