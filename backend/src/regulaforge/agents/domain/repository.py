"""Repository interfaces for the Multi-Agent AI System.

Defines the contract for persisting and querying agent tasks
and workflow executions without coupling to any specific
infrastructure implementation.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from uuid import UUID

from regulaforge.agents.domain.models import (
    AgentTask,
    AgentType,
    TaskStatus,
    WorkflowExecution,
)


class AgentTaskRepository(ABC):
    """Repository interface for AgentTask persistence and querying."""

    @abstractmethod
    async def save(self, task: AgentTask) -> AgentTask:
        """Persist a new or updated agent task.

        Args:
            task: The agent task to save.

        Returns:
            The saved task with any generated fields populated.

        Raises:
            RuntimeError: If persistence fails.
        """
        ...

    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> Optional[AgentTask]:
        """Retrieve a task by its unique identifier.

        Args:
            task_id: The task UUID.

        Returns:
            The task if found, None otherwise.
        """
        ...

    @abstractmethod
    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentTask], int]:
        """Search tasks with filtering and pagination.

        Supported filters:
            - agent_type (AgentType or str)
            - task_type (str)
            - status (TaskStatus or str)
            - priority_min (int)
            - priority_max (int)
            - correlation_id (str)
            - created_after (datetime)
            - created_before (datetime)

        Args:
            filters: Dictionary of field filters.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            A tuple of (tasks list, total count).

        Raises:
            ValueError: If page or page_size are invalid.
            RuntimeError: If the search fails.
        """
        ...

    @abstractmethod
    async def get_pending(
        self,
        agent_type: AgentType,
        limit: int = 10,
    ) -> list[AgentTask]:
        """Get pending tasks for a specific agent type, ordered by priority.

        Args:
            agent_type: The agent type to fetch tasks for.
            limit: Maximum number of tasks to return.

        Returns:
            A list of pending tasks ordered by priority (highest first).
        """
        ...

    @abstractmethod
    async def update_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        error: Optional[str] = None,
        output_data: Optional[dict[str, Any]] = None,
    ) -> Optional[AgentTask]:
        """Update the status and related fields of a task.

        Args:
            task_id: The task UUID.
            status: New task status.
            error: Error message if status is FAILED.
            output_data: Output data if status is COMPLETED.

        Returns:
            The updated task if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_by_correlation_id(self, correlation_id: str) -> list[AgentTask]:
        """Retrieve all tasks associated with a correlation ID.

        Args:
            correlation_id: The correlation ID to search for.

        Returns:
            A list of tasks sharing the given correlation ID.
        """
        ...


class WorkflowExecutionRepository(ABC):
    """Repository interface for WorkflowExecution persistence and querying."""

    @abstractmethod
    async def save(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Persist a new or updated workflow execution.

        Args:
            execution: The workflow execution to save.

        Returns:
            The saved execution with any generated fields populated.

        Raises:
            RuntimeError: If persistence fails.
        """
        ...

    @abstractmethod
    async def get_by_id(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Retrieve a workflow execution by its unique identifier.

        Args:
            execution_id: The execution UUID.

        Returns:
            The execution if found, None otherwise.
        """
        ...

    @abstractmethod
    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WorkflowExecution], int]:
        """Search workflow executions with filtering and pagination.

        Supported filters:
            - workflow_id (UUID)
            - status (TaskStatus or str)
            - started_after (datetime)
            - started_before (datetime)

        Args:
            filters: Dictionary of field filters.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            A tuple of (executions list, total count).
        """
        ...

    @abstractmethod
    async def update_step(
        self,
        execution_id: UUID,
        step: int,
        result: dict[str, Any],
    ) -> Optional[WorkflowExecution]:
        """Update the current step and accumulated results of an execution.

        Args:
            execution_id: The execution UUID.
            step: The completed step order.
            result: The result data from the completed step.

        Returns:
            The updated execution if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_running(self) -> list[WorkflowExecution]:
        """Get all currently running workflow executions.

        Returns:
            A list of executions with status IN_PROGRESS.
        """
        ...
