"""Core orchestrator for the Multi-Agent AI System.

The AgentOrchestrator is the central coordinator responsible for
task dispatching, workflow execution, agent registration, and
lifecycle management of all AI agents in the system.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from regulaforge.agents.application.agent_base import BaseAgent
from regulaforge.agents.domain.events import (
    AgentOverloaded,
    TaskAssigned,
    TaskCompleted,
    TaskCreated,
    TaskFailed,
    TaskRetrying,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
    WorkflowStepCompleted,
)
from regulaforge.agents.domain.models import (
    AgentCapability,
    AgentStatus,
    AgentTask,
    AgentType,
    TaskStatus,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStep,
)
from regulaforge.agents.domain.repository import (
    AgentTaskRepository,
    WorkflowExecutionRepository,
)
from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    """Central coordinator for the multi-agent AI system.

    Manages agent registration, task submission and dispatch,
    workflow orchestration, health monitoring, and lifecycle
    events across all agents in the system.
    """

    def __init__(
        self,
        task_repository: AgentTaskRepository,
        workflow_repository: WorkflowExecutionRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._task_repository = task_repository
        self._workflow_repository = workflow_repository
        self._event_publisher = event_publisher

        self._agents: dict[AgentType, BaseAgent] = {}
        self._handlers: dict[AgentType, Callable] = {}
        self._agent_statuses: dict[AgentType, AgentStatus] = {}
        self._agent_active_tasks: dict[AgentType, int] = {}
        self._agent_capabilities: dict[AgentType, AgentCapability] = {}
        self._workflow_executions: dict[UUID, WorkflowExecution] = {}
        self._running_workflows: dict[UUID, asyncio.Task] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

        logger.info("AgentOrchestrator initialized")

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent instance with the orchestrator.

        The agent's capabilities and handler are registered so
        the orchestrator can dispatch tasks to it.

        Args:
            agent: The agent instance to register.
        """
        agent_type = agent.agent_type
        self._agents[agent_type] = agent
        self._agent_statuses[agent_type] = AgentStatus.IDLE
        self._agent_active_tasks[agent_type] = 0
        self._agent_capabilities[agent_type] = agent.get_capabilities()

        logger.info(
            "Agent registered: %s (capabilities: %s)",
            agent_type.value,
            list(agent.get_capabilities().task_types),
        )

    def register_handler(self, agent_type: AgentType, handler: Callable) -> None:
        """Register a handler function for a given agent type.

        Args:
            agent_type: The agent type this handler serves.
            handler: An async callable that accepts an AgentTask and returns a dict.
        """
        self._handlers[agent_type] = handler
        self._agent_statuses[agent_type] = AgentStatus.IDLE
        self._agent_active_tasks[agent_type] = 0
        logger.info("Handler registered for agent type: %s", agent_type.value)

    async def submit_task(self, task: AgentTask) -> AgentTask:
        """Submit a task for execution by the appropriate agent.

        The task is persisted, a TaskCreated event is published,
        and the task is immediately dispatched if possible.

        Args:
            task: The task to submit.

        Returns:
            The saved task with any generated fields.

        Raises:
            ValueError: If required task fields are missing.
            RuntimeError: If task submission fails.
        """
        if not task.task_type:
            raise ValueError("task_type is required")
        if not task.agent_type:
            raise ValueError("agent_type is required")

        try:
            saved_task = await self._task_repository.save(task)

            await self._event_publisher.publish(
                TaskCreated(
                    task_id=saved_task.id,
                    agent_type=saved_task.agent_type.value,
                    task_type=saved_task.task_type,
                    correlation_id=saved_task.correlation_id,
                )
            )

            await self.dispatch_task(saved_task)

            logger.info(
                "Task submitted: id=%s type=%s agent=%s priority=%d",
                saved_task.id,
                saved_task.task_type,
                saved_task.agent_type.value,
                saved_task.priority,
            )
            return saved_task
        except Exception as exc:
            logger.error("Failed to submit task: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to submit task: {exc}") from exc

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        input_data: dict[str, Any],
    ) -> WorkflowExecution:
        """Submit a multi-step workflow for execution.

        Creates a WorkflowExecution, publishes the start event,
        and begins executing steps sequentially.

        Args:
            workflow: The workflow definition to execute.
            input_data: Initial input data for the first step.

        Returns:
            The workflow execution tracking object.

        Raises:
            ValueError: If workflow has no steps.
            RuntimeError: If workflow submission fails.
        """
        if not workflow.steps:
            raise ValueError("Workflow must have at least one step")

        try:
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                status=TaskStatus.IN_PROGRESS,
                current_step=0,
                steps=[step.to_dict() if hasattr(step, 'to_dict') else {
                    "order": step.order,
                    "agent_type": step.agent_type.value,
                    "task_type": step.task_type,
                    "input_mapping": step.input_mapping,
                    "output_mapping": step.output_mapping,
                    "timeout_seconds": step.timeout_seconds,
                    "retry_count": step.retry_count,
                    "on_failure": step.on_failure,
                } for step in workflow.steps],
                results={"initial": input_data},
                started_at=datetime.now(timezone.utc),
            )

            saved_execution = await self._workflow_repository.save(execution)
            self._workflow_executions[saved_execution.id] = saved_execution

            await self._event_publisher.publish(
                WorkflowStarted(
                    execution_id=saved_execution.id,
                    workflow_id=workflow.id,
                    workflow_name=workflow.name,
                )
            )

            workflow_task = asyncio.create_task(
                self._execute_workflow_steps(saved_execution, workflow, input_data)
            )
            self._running_workflows[saved_execution.id] = workflow_task

            logger.info(
                "Workflow submitted: id=%s name=%s steps=%d",
                saved_execution.id,
                workflow.name,
                len(workflow.steps),
            )
            return saved_execution
        except Exception as exc:
            logger.error("Failed to submit workflow: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to submit workflow: {exc}") from exc

    async def dispatch_task(self, task: AgentTask) -> None:
        """Find the best available agent and assign the task for execution.

        Marks the task as ASSIGNED, publishes the event, and
        invokes the agent's handler asynchronously.

        Args:
            task: The task to dispatch.
        """
        agent_type = task.agent_type
        agent = self._agents.get(agent_type)
        handler = self._handlers.get(agent_type)

        if agent is None and handler is None:
            logger.warning(
                "No agent or handler registered for type: %s",
                agent_type.value,
            )
            await self._task_repository.update_status(
                task.id, TaskStatus.FAILED, error=f"No agent available for {agent_type.value}"
            )
            return

        if agent and self._agent_statuses.get(agent_type) == AgentStatus.DISABLED:
            logger.warning("Agent %s is disabled, cannot dispatch task", agent_type.value)
            await self._task_repository.update_status(
                task.id, TaskStatus.FAILED, error=f"Agent {agent_type.value} is disabled"
            )
            return

        current_tasks = self._agent_active_tasks.get(agent_type, 0)
        capability = self._agent_capabilities.get(agent_type)
        if capability and current_tasks >= capability.max_concurrent_tasks:
            logger.warning(
                "Agent %s overloaded: %d/%d tasks",
                agent_type.value,
                current_tasks,
                capability.max_concurrent_tasks,
            )
            await self._event_publisher.publish(
                AgentOverloaded(
                    agent_type=agent_type.value,
                    current_tasks=current_tasks,
                    max_concurrent=capability.max_concurrent_tasks,
                )
            )
            return

        await self._task_repository.update_status(task.id, TaskStatus.ASSIGNED)
        self._agent_statuses[agent_type] = AgentStatus.BUSY
        async with self._lock:
            self._agent_active_tasks[agent_type] = current_tasks + 1

        await self._event_publisher.publish(
            TaskAssigned(
                task_id=task.id,
                agent_type=agent_type.value,
                handler_name=agent.__class__.__name__ if agent else "handler",
            )
        )

        asyncio.create_task(self._execute_task(task, agent, handler))  # noqa: RUF006

    async def handle_task_completion(
        self,
        task_id: UUID,
        result: dict[str, Any],
    ) -> Optional[AgentTask]:
        """Process the successful completion of a task.

        Updates the task status, publishes the completion event,
        and advances any associated workflow.

        Args:
            task_id: The completed task's UUID.
            result: The output data produced by the agent.

        Returns:
            The updated task, or None if not found.
        """
        try:
            task = await self._task_repository.update_status(
                task_id, TaskStatus.COMPLETED, output_data=result
            )
            if task is None:
                logger.warning("Task %s not found for completion handling", task_id)
                return None

            agent_type = task.agent_type
            async with self._lock:
                self._agent_active_tasks[agent_type] = max(
                    0, self._agent_active_tasks.get(agent_type, 0) - 1
                )
                if self._agent_active_tasks.get(agent_type, 0) == 0:
                    self._agent_statuses[agent_type] = AgentStatus.IDLE

            await self._event_publisher.publish(
                TaskCompleted(
                    task_id=task.id,
                    agent_type=agent_type.value,
                    task_type=task.task_type,
                    output_summary=str(result)[:200],
                    correlation_id=task.correlation_id,
                )
            )

            await self._advance_workflow(task.correlation_id, task_id, result)

            logger.info(
                "Task completed: id=%s agent=%s output_keys=%s",
                task_id,
                agent_type.value,
                list(result.keys()) if result else [],
            )
            return task
        except Exception as exc:
            logger.error("Failed to handle task completion: %s", exc, exc_info=True)
            return None

    async def handle_task_failure(
        self,
        task_id: UUID,
        error: str,
    ) -> Optional[AgentTask]:
        """Handle a task failure with retry logic and escalation.

        Applies the task's retry policy, and if retries are exhausted,
        marks the task as failed and publishes the failure event.

        Args:
            task_id: The failed task's UUID.
            error: Error description.

        Returns:
            The updated task, or None if not found.
        """
        try:
            task = await self._task_repository.get_by_id(task_id)
            if task is None:
                logger.warning("Task %s not found for failure handling", task_id)
                return None

            agent_type = task.agent_type
            self._agent_active_tasks[agent_type] = max(
                0, self._agent_active_tasks.get(agent_type, 0) - 1
            )
            if self._agent_active_tasks.get(agent_type, 0) == 0:
                self._agent_statuses[agent_type] = AgentStatus.IDLE

            task = await self._task_repository.update_status(
                task_id, TaskStatus.FAILED, error=error
            )

            await self._event_publisher.publish(
                TaskFailed(
                    task_id=task_id,
                    agent_type=agent_type.value,
                    task_type=task.task_type if task else "unknown",
                    error_message=error,
                    correlation_id=task.correlation_id if task else None,
                )
            )

            await self._handle_workflow_step_failure(
                task.correlation_id if task else "",
                task_id,
                error,
            )

            logger.error("Task failed: id=%s agent=%s error=%s", task_id, agent_type.value, error)
            return task
        except Exception as exc:
            logger.error("Failed to handle task failure: %s", exc, exc_info=True)
            return None

    def get_agent_health(self) -> dict[str, dict[str, Any]]:
        """Get detailed health status of all registered agents.

        Returns:
            A dictionary mapping agent type names to their health data.
        """
        health: dict[str, dict[str, Any]] = {}
        for agent_type in AgentType:
            status = self._agent_statuses.get(agent_type, AgentStatus.DISABLED)
            active = self._agent_active_tasks.get(agent_type, 0)
            capability = self._agent_capabilities.get(agent_type)

            health[agent_type.value] = {
                "status": status.value,
                "active_tasks": active,
                "max_concurrent": capability.max_concurrent_tasks if capability else 0,
                "has_handler": agent_type in self._handlers or agent_type in self._agents,
            }
        return health

    async def get_workflow_status(
        self,
        workflow_execution_id: UUID,
    ) -> Optional[dict[str, Any]]:
        """Get the current status and progress of a workflow execution.

        Args:
            workflow_execution_id: The execution UUID.

        Returns:
            A dictionary with workflow status data, or None if not found.
        """
        execution = await self._workflow_repository.get_by_id(workflow_execution_id)
        if execution is None:
            return None
        return {
            "id": str(execution.id),
            "workflow_id": str(execution.workflow_id),
            "status": execution.status.value,
            "current_step": execution.current_step,
            "total_steps": len(execution.steps),
            "step_count": len(execution.steps),
            "results_keys": list(execution.results.keys()),
            "error_count": len(execution.errors),
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        }

    async def cancel_task(self, task_id: UUID) -> Optional[AgentTask]:
        """Cancel a running task by setting its status to CANCELLED.

        Args:
            task_id: The task UUID to cancel.

        Returns:
            The cancelled task, or None if not found.
        """
        task = await self._task_repository.update_status(task_id, TaskStatus.CANCELLED)
        if task:
            agent_type = task.agent_type
            self._agent_active_tasks[agent_type] = max(
                0, self._agent_active_tasks.get(agent_type, 0) - 1
            )
            logger.info("Task cancelled: id=%s", task_id)
        return task

    async def pause_workflow(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Pause a running workflow execution.

        The workflow will stop advancing to the next step until resumed.

        Args:
            execution_id: The execution UUID to pause.

        Returns:
            The paused execution, or None if not found.
        """
        execution = await self._workflow_repository.get_by_id(execution_id)
        if execution is None:
            logger.warning("Workflow execution %s not found", execution_id)
            return None

        if execution.status != TaskStatus.IN_PROGRESS:
            logger.warning(
                "Cannot pause workflow %s: status is %s",
                execution_id,
                execution.status.value,
            )
            return None

        execution.status = TaskStatus.CANCELLED
        saved = await self._workflow_repository.save(execution)

        running_task = self._running_workflows.get(execution_id)
        if running_task and not running_task.done():
            running_task.cancel()

        logger.info("Workflow paused: id=%s", execution_id)
        return saved

    async def _execute_task(
        self,
        task: AgentTask,
        agent: Optional[BaseAgent],
        handler: Optional[Callable],
    ) -> None:
        """Execute a task via the registered agent or handler.

        Handles the full lifecycle: in-progress marking, execution,
        completion/failure processing, and retry logic.

        Args:
            task: The task to execute.
            agent: The registered agent instance, if any.
            handler: The registered handler function, if any.
        """
        try:
            await self._task_repository.update_status(task.id, TaskStatus.IN_PROGRESS)

            if agent is not None:
                result = await agent.execute(task)
            elif handler is not None:
                result = await handler(task)
            else:
                raise RuntimeError(f"No handler or agent for task {task.id}")

            await self.handle_task_completion(task.id, result)
        except asyncio.CancelledError:
            logger.info("Task execution cancelled: id=%s", task.id)
            await self._task_repository.update_status(
                task.id, TaskStatus.CANCELLED, error="Execution cancelled"
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.error("Task execution failed: id=%s error=%s", task.id, error_msg)

            retry_count = getattr(task, '_retry_count', 0)
            max_retries = getattr(task, '_max_retries', 3)

            if retry_count < max_retries:
                task._retry_count = retry_count + 1
                backoff = 2.0 ** retry_count
                await self._event_publisher.publish(
                    TaskRetrying(
                        task_id=task.id,
                        agent_type=task.agent_type.value,
                        attempt=retry_count + 1,
                        max_retries=max_retries,
                        error_message=error_msg,
                        correlation_id=task.correlation_id,
                    )
                )
                logger.info(
                    "Retrying task %s (attempt %d/%d) after %.1fs",
                    task.id,
                    retry_count + 1,
                    max_retries,
                    backoff,
                )
                await asyncio.sleep(backoff)
                await self._execute_task(task, agent, handler)
            else:
                await self.handle_task_failure(task.id, error_msg)

    async def _execute_workflow_steps(
        self,
        execution: WorkflowExecution,
        workflow: WorkflowDefinition,
        input_data: dict[str, Any],
    ) -> None:
        """Execute the steps of a workflow sequentially.

        Args:
            execution: The workflow execution tracking object.
            workflow: The workflow definition.
            input_data: Initial input data for the workflow.
        """
        accumulated_data = dict(input_data)

        try:
            for step_index, step in enumerate(workflow.steps):
                execution.current_step = step_index
                await self._workflow_repository.save(execution)

                step_input = self._apply_input_mapping(step, accumulated_data)

                task = AgentTask(
                    agent_type=step.agent_type,
                    task_type=step.task_type,
                    input_data=step_input,
                    priority=5,
                    correlation_id=str(execution.id),
                    retry_count=0,
                    max_retries=step.retry_count,
                )

                saved_task = await self._task_repository.save(task)
                await self.dispatch_task(saved_task)

                task_result = await self._wait_for_task_result(saved_task.id, step.timeout_seconds)

                if task_result is None:
                    error_msg = f"Step {step_index} timed out after {step.timeout_seconds}s"
                    if step.on_failure == "abort":
                        execution.errors[str(step_index)] = error_msg
                        execution.status = TaskStatus.FAILED
                        execution.completed_at = datetime.now(timezone.utc)
                        await self._workflow_repository.save(execution)
                        await self._event_publisher.publish(
                            WorkflowFailed(
                                execution_id=execution.id,
                                workflow_id=workflow.id,
                                failed_step=step_index,
                                error_message=error_msg,
                            )
                        )
                        return
                    elif step.on_failure == "skip":
                        logger.warning("Skipping failed step %d: %s", step_index, error_msg)
                        continue
                    elif step.on_failure == "retry":
                        for attempt in range(step.retry_count):
                            await asyncio.sleep(2.0 ** attempt)
                            retry_task = AgentTask(
                                agent_type=step.agent_type,
                                task_type=step.task_type,
                                input_data=step_input,
                                priority=5,
                                correlation_id=str(execution.id),
                            )
                            retry_saved = await self._task_repository.save(retry_task)
                            await self.dispatch_task(retry_saved)
                            retry_result = await self._wait_for_task_result(
                                retry_saved.id, step.timeout_seconds
                            )
                            if retry_result is not None:
                                task_result = retry_result
                                break
                        if task_result is None:
                            execution.errors[str(step_index)] = error_msg
                            execution.status = TaskStatus.FAILED
                            execution.completed_at = datetime.now(timezone.utc)
                            await self._workflow_repository.save(execution)
                            await self._event_publisher.publish(
                                WorkflowFailed(
                                    execution_id=execution.id,
                                    workflow_id=workflow.id,
                                    failed_step=step_index,
                                    error_message=error_msg,
                                )
                            )
                            return

                step_output = self._apply_output_mapping(step, task_result)
                accumulated_data.update(step_output)
                execution.results[f"step_{step_index}"] = task_result

                await self._workflow_repository.update_step(execution.id, step_index, task_result)
                await self._event_publisher.publish(
                    WorkflowStepCompleted(
                        execution_id=execution.id,
                        workflow_id=workflow.id,
                        step_order=step_index,
                        agent_type=step.agent_type.value,
                        task_id=saved_task.id,
                    )
                )

                logger.info(
                    "Workflow step completed: exec=%s step=%d/%d agent=%s",
                    execution.id,
                    step_index + 1,
                    len(workflow.steps),
                    step.agent_type.value,
                )

            execution.status = TaskStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            await self._workflow_repository.save(execution)
            await self._event_publisher.publish(
                WorkflowCompleted(
                    execution_id=execution.id,
                    workflow_id=workflow.id,
                    step_count=len(workflow.steps),
                )
            )
            logger.info("Workflow completed: id=%s", execution.id)

        except asyncio.CancelledError:
            execution.status = TaskStatus.CANCELLED
            execution.completed_at = datetime.now(timezone.utc)
            await self._workflow_repository.save(execution)
            logger.info("Workflow cancelled: id=%s", execution.id)
        except Exception as exc:
            logger.error("Workflow execution failed: %s", exc, exc_info=True)
            execution.status = TaskStatus.FAILED
            execution.completed_at = datetime.now(timezone.utc)
            await self._workflow_repository.save(execution)
            await self._event_publisher.publish(
                WorkflowFailed(
                    execution_id=execution.id,
                    workflow_id=workflow.id,
                    failed_step=execution.current_step,
                    error_message=str(exc),
                )
            )

    async def _wait_for_task_result(
        self,
        task_id: UUID,
        timeout_seconds: int,
    ) -> Optional[dict[str, Any]]:
        """Wait for a task to complete with a timeout.

        Polls the task repository at intervals until the task
        completes, fails, or the timeout is reached.

        Args:
            task_id: The task UUID to wait for.
            timeout_seconds: Maximum time to wait in seconds.

        Returns:
            The task's output data if completed, None otherwise.
        """
        poll_interval = 1.0
        elapsed = 0.0

        while elapsed < timeout_seconds:
            task = await self._task_repository.get_by_id(task_id)
            if task is None:
                return None
            if task.status == TaskStatus.COMPLETED:
                return task.output_data
            if task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                return None
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return None

    async def _advance_workflow(
        self,
        correlation_id: str,
        _completed_task_id: UUID,
        _result: dict[str, Any],
    ) -> None:
        """Advance a workflow to its next step after a task completes.

        Args:
            correlation_id: The correlation ID linking the task to its workflow.
            completed_task_id: The completed task's UUID.
            result: The task's output data.
        """
        if not correlation_id:
            return

        try:
            execution_id = UUID(correlation_id)
        except (ValueError, TypeError):
            return

        execution = self._workflow_executions.get(execution_id)
        if execution is None:
            return

        workflow = WORKFLOW_REGISTRY.get(execution.workflow_id)  # noqa: F821
        if workflow is None:
            return

        next_step = execution.current_step + 1
        if next_step >= len(workflow.steps):
            execution.status = TaskStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            await self._workflow_repository.save(execution)
            await self._event_publisher.publish(
                WorkflowCompleted(
                    execution_id=execution.id,
                    workflow_id=workflow.id,
                    step_count=len(workflow.steps),
                )
            )
            logger.info("Workflow completed: id=%s", execution.id)
            return

        step = workflow.steps[next_step]
        execution.current_step = next_step
        await self._workflow_repository.save(execution)

        accumulated_data = dict(execution.results)
        step_input = self._apply_input_mapping(step, accumulated_data)

        task = AgentTask(
            agent_type=step.agent_type,
            task_type=step.task_type,
            input_data=step_input,
            priority=5,
            correlation_id=str(execution.id),
            retry_count=0,
            max_retries=step.retry_count,
        )
        saved_task = await self._task_repository.save(task)
        await self.dispatch_task(saved_task)

        logger.debug(
            "Advanced workflow %s to step %d via task %s",
            execution_id,
            next_step,
            saved_task.id,
        )

    async def _handle_workflow_step_failure(
        self,
        correlation_id: str,
        failed_task_id: UUID,
        error: str,
    ) -> None:
        """Handle a task failure within a workflow context.

        Args:
            correlation_id: The correlation ID linking the task to its workflow.
            failed_task_id: The failed task's UUID.
            error: Error description.
        """
        if not correlation_id:
            return

        try:
            execution_id = UUID(correlation_id)
        except (ValueError, TypeError):
            return

        execution = self._workflow_executions.get(execution_id)
        if execution is None:
            return

        if execution.status == TaskStatus.IN_PROGRESS:
            execution.status = TaskStatus.FAILED
            execution.completed_at = datetime.now(timezone.utc)
            execution.errors[str(execution.current_step)] = error
            await self._workflow_repository.save(execution)
            await self._event_publisher.publish(
                WorkflowFailed(
                    execution_id=execution.id,
                    workflow_id=execution.workflow_id,
                    failed_step=execution.current_step,
                    error_message=error,
                )
            )
            logger.warning(
                "Workflow %s marked as FAILED at step %d: task=%s error=%s",
                execution_id,
                execution.current_step,
                failed_task_id,
                error,
            )

    @staticmethod
    def _apply_input_mapping(
        step: WorkflowStep,
        accumulated_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply input mapping from accumulated data to step input.

        Args:
            step: The workflow step being executed.
            accumulated_data: Data accumulated from previous steps.

        Returns:
            The mapped input data for the step.
        """
        if not step.input_mapping:
            return dict(accumulated_data)

        mapped = {}
        for step_key, source_key in step.input_mapping.items():
            mapped[step_key] = accumulated_data.get(source_key)
        return mapped

    @staticmethod
    def _apply_output_mapping(
        step: WorkflowStep,
        step_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply output mapping from step result to accumulated data.

        Args:
            step: The workflow step that completed.
            step_result: The result data from the step.

        Returns:
            The mapped output data.
        """
        if not step.output_mapping:
            return dict(step_result)

        mapped = {}
        for result_key, output_key in step.output_mapping.items():
            mapped[output_key] = step_result.get(result_key)
        return mapped
