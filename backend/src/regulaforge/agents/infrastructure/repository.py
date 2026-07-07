"""SQLAlchemy-based repository implementations for the Multi-Agent AI System.

Implements the repository interfaces defined in the domain layer
using SQLAlchemy async sessions for PostgreSQL persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from regulaforge.agents.domain.models import (
    AgentTask,
    AgentType,
    TaskStatus,
    WorkflowExecution,
)
from regulaforge.agents.domain.repository import (
    AgentTaskRepository,
    WorkflowExecutionRepository,
)
from regulaforge.agents.infrastructure.models import (
    AgentTaskModel,
    WorkflowExecutionModel,
)
from regulaforge.config.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyAgentTaskRepository(AgentTaskRepository):
    """SQLAlchemy implementation of AgentTaskRepository.

    Persists and queries agent tasks using async SQLAlchemy sessions
    with proper error handling and logging.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, task: AgentTask) -> AgentTask:
        try:
            existing = await self._session.get(AgentTaskModel, task.id)
            if existing:
                self._update_model(existing, task)
            else:
                model = self._task_to_model(task)
                self._session.add(model)

            await self._session.flush()
            logger.debug("Task saved: id=%s status=%s", task.id, task.status.value)
            return task
        except Exception as exc:
            logger.error("Failed to save task %s: %s", task.id, exc, exc_info=True)
            raise RuntimeError(f"Failed to save task: {exc}") from exc

    async def get_by_id(self, task_id: UUID) -> Optional[AgentTask]:
        try:
            model = await self._session.get(AgentTaskModel, task_id)
            if model is None:
                return None
            return self._model_to_task(model)
        except Exception as exc:
            logger.error("Failed to get task %s: %s", task_id, exc, exc_info=True)
            raise RuntimeError(f"Failed to get task: {exc}") from exc

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[AgentTask], int]:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

        try:
            query = self._build_search_query(filters or {})
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self._session.execute(count_query)
            total_count = total_result.scalar_one()

            offset = (page - 1) * page_size
            paginated_query = query.order_by(AgentTaskModel.priority.desc(), AgentTaskModel.created_at.desc()).offset(offset).limit(page_size)  # noqa: E501
            result = await self._session.execute(paginated_query)
            models = result.scalars().all()

            tasks = [self._model_to_task(m) for m in models]
            logger.debug("Task search returned %d of %d results", len(tasks), total_count)
            return tasks, total_count
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to search tasks: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to search tasks: {exc}") from exc

    async def get_pending(
        self,
        agent_type: AgentType,
        limit: int = 10,
    ) -> list[AgentTask]:
        try:
            query = (
                select(AgentTaskModel)
                .where(
                    and_(
                        AgentTaskModel.agent_type == agent_type.value,
                        AgentTaskModel.status == TaskStatus.PENDING.value,
                    )
                )
                .order_by(AgentTaskModel.priority.desc(), AgentTaskModel.created_at.asc())
                .limit(limit)
            )
            result = await self._session.execute(query)
            models = result.scalars().all()
            return [self._model_to_task(m) for m in models]
        except Exception as exc:
            logger.error("Failed to get pending tasks for %s: %s", agent_type.value, exc, exc_info=True)
            raise RuntimeError(f"Failed to get pending tasks: {exc}") from exc

    async def update_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        error: Optional[str] = None,
        output_data: Optional[dict[str, Any]] = None,
    ) -> Optional[AgentTask]:
        try:
            model = await self._session.get(AgentTaskModel, task_id)
            if model is None:
                return None

            model.status = status.value
            if error is not None:
                model.error = error
            if output_data is not None:
                model.output_data = output_data
            if status == TaskStatus.IN_PROGRESS:
                model.started_at = datetime.now(timezone.utc)
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                model.completed_at = datetime.now(timezone.utc)

            await self._session.flush()
            logger.debug("Task %s status updated to %s", task_id, status.value)
            return self._model_to_task(model)
        except Exception as exc:
            logger.error("Failed to update task %s status: %s", task_id, exc, exc_info=True)
            raise RuntimeError(f"Failed to update task status: {exc}") from exc

    async def get_by_correlation_id(self, correlation_id: str) -> list[AgentTask]:
        try:
            query = select(AgentTaskModel).where(
                AgentTaskModel.correlation_id == correlation_id
            ).order_by(AgentTaskModel.created_at.asc())
            result = await self._session.execute(query)
            models = result.scalars().all()
            return [self._model_to_task(m) for m in models]
        except Exception as exc:
            logger.error("Failed to get tasks by correlation_id %s: %s", correlation_id, exc, exc_info=True)
            raise RuntimeError(f"Failed to get tasks by correlation_id: {exc}") from exc

    def _build_search_query(self, filters: dict[str, Any]) -> Select:
        conditions = []

        agent_type = filters.get("agent_type")
        if agent_type is not None:
            if isinstance(agent_type, AgentType):
                conditions.append(AgentTaskModel.agent_type == agent_type.value)
            else:
                conditions.append(AgentTaskModel.agent_type == str(agent_type))

        task_type = filters.get("task_type")
        if task_type is not None:
            conditions.append(AgentTaskModel.task_type == str(task_type))

        status = filters.get("status")
        if status is not None:
            if isinstance(status, TaskStatus):
                conditions.append(AgentTaskModel.status == status.value)
            else:
                conditions.append(AgentTaskModel.status == str(status))

        priority_min = filters.get("priority_min")
        if priority_min is not None:
            conditions.append(AgentTaskModel.priority >= int(priority_min))

        priority_max = filters.get("priority_max")
        if priority_max is not None:
            conditions.append(AgentTaskModel.priority <= int(priority_max))

        correlation_id = filters.get("correlation_id")
        if correlation_id is not None:
            conditions.append(AgentTaskModel.correlation_id == str(correlation_id))

        created_after = filters.get("created_after")
        if created_after is not None:
            conditions.append(AgentTaskModel.created_at >= created_after)

        created_before = filters.get("created_before")
        if created_before is not None:
            conditions.append(AgentTaskModel.created_at <= created_before)

        return select(AgentTaskModel).where(and_(*conditions)) if conditions else select(AgentTaskModel)

    @staticmethod
    def _task_to_model(task: AgentTask) -> AgentTaskModel:
        return AgentTaskModel(
            id=task.id,
            agent_type=task.agent_type.value,
            task_type=task.task_type,
            input_data=task.input_data,
            priority=task.priority,
            status=task.status.value,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error=task.error,
            output_data=task.output_data,
            correlation_id=task.correlation_id,
            created_at=task.created_at,
        )

    @staticmethod
    def _model_to_task(model: AgentTaskModel) -> AgentTask:
        return AgentTask(
            id=model.id,
            agent_type=AgentType(model.agent_type),
            task_type=model.task_type,
            input_data=model.input_data or {},
            priority=model.priority,
            status=TaskStatus(model.status),
            created_at=model.created_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error=model.error,
            output_data=model.output_data,
            correlation_id=model.correlation_id or "",
        )

    @staticmethod
    def _update_model(model: AgentTaskModel, task: AgentTask) -> None:
        model.agent_type = task.agent_type.value
        model.task_type = task.task_type
        model.input_data = task.input_data
        model.priority = task.priority
        model.status = task.status.value
        model.started_at = task.started_at
        model.completed_at = task.completed_at
        model.error = task.error
        model.output_data = task.output_data
        model.correlation_id = task.correlation_id


class SqlAlchemyWorkflowExecutionRepository(WorkflowExecutionRepository):
    """SQLAlchemy implementation of WorkflowExecutionRepository.

    Persists and queries workflow execution state using async
    SQLAlchemy sessions with proper error handling and logging.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, execution: WorkflowExecution) -> WorkflowExecution:
        try:
            existing = await self._session.get(WorkflowExecutionModel, execution.id)
            if existing:
                self._update_model(existing, execution)
            else:
                model = self._execution_to_model(execution)
                self._session.add(model)

            await self._session.flush()
            logger.debug("Execution saved: id=%s status=%s", execution.id, execution.status.value)
            return execution
        except Exception as exc:
            logger.error("Failed to save execution %s: %s", execution.id, exc, exc_info=True)
            raise RuntimeError(f"Failed to save execution: {exc}") from exc

    async def get_by_id(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        try:
            model = await self._session.get(WorkflowExecutionModel, execution_id)
            if model is None:
                return None
            return self._model_to_execution(model)
        except Exception as exc:
            logger.error("Failed to get execution %s: %s", execution_id, exc, exc_info=True)
            raise RuntimeError(f"Failed to get execution: {exc}") from exc

    async def search(
        self,
        filters: Optional[dict[str, Any]] = None,
        page: int = DEFAULT_PAGE,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[WorkflowExecution], int]:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

        try:
            query = self._build_search_query(filters or {})
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self._session.execute(count_query)
            total_count = total_result.scalar_one()

            offset = (page - 1) * page_size
            paginated_query = query.order_by(
                WorkflowExecutionModel.created_at.desc()
            ).offset(offset).limit(page_size)
            result = await self._session.execute(paginated_query)
            models = result.scalars().all()

            executions = [self._model_to_execution(m) for m in models]
            return executions, total_count
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to search executions: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to search executions: {exc}") from exc

    async def update_step(
        self,
        execution_id: UUID,
        step: int,
        result: dict[str, Any],
    ) -> Optional[WorkflowExecution]:
        try:
            model = await self._session.get(WorkflowExecutionModel, execution_id)
            if model is None:
                return None

            model.current_step = step + 1
            results = dict(model.results or {})
            results[f"step_{step}"] = result
            model.results = results

            await self._session.flush()
            logger.debug("Execution %s step %d updated", execution_id, step)
            return self._model_to_execution(model)
        except Exception as exc:
            logger.error("Failed to update execution %s step: %s", execution_id, exc, exc_info=True)
            raise RuntimeError(f"Failed to update execution step: {exc}") from exc

    async def get_running(self) -> list[WorkflowExecution]:
        try:
            query = select(WorkflowExecutionModel).where(
                WorkflowExecutionModel.status == TaskStatus.IN_PROGRESS.value
            ).order_by(WorkflowExecutionModel.created_at.asc())
            result = await self._session.execute(query)
            models = result.scalars().all()
            return [self._model_to_execution(m) for m in models]
        except Exception as exc:
            logger.error("Failed to get running executions: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to get running executions: {exc}") from exc

    def _build_search_query(self, filters: dict[str, Any]) -> Select:
        conditions = []

        workflow_id = filters.get("workflow_id")
        if workflow_id is not None:
            conditions.append(WorkflowExecutionModel.workflow_id == workflow_id)

        status = filters.get("status")
        if status is not None:
            if isinstance(status, TaskStatus):
                conditions.append(WorkflowExecutionModel.status == status.value)
            else:
                conditions.append(WorkflowExecutionModel.status == str(status))

        started_after = filters.get("started_after")
        if started_after is not None:
            conditions.append(WorkflowExecutionModel.started_at >= started_after)

        started_before = filters.get("started_before")
        if started_before is not None:
            conditions.append(WorkflowExecutionModel.started_at <= started_before)

        return select(WorkflowExecutionModel).where(and_(*conditions)) if conditions else select(WorkflowExecutionModel)

    @staticmethod
    def _execution_to_model(execution: WorkflowExecution) -> WorkflowExecutionModel:
        return WorkflowExecutionModel(
            id=execution.id,
            workflow_id=execution.workflow_id,
            status=execution.status.value,
            current_step=execution.current_step,
            steps=[dict(s) if isinstance(s, dict) else s for s in execution.steps],
            results=dict(execution.results),
            errors=dict(execution.errors),
            started_at=execution.started_at,
            completed_at=execution.completed_at,
        )

    @staticmethod
    def _model_to_execution(model: WorkflowExecutionModel) -> WorkflowExecution:
        return WorkflowExecution(
            id=model.id,
            workflow_id=model.workflow_id,
            status=TaskStatus(model.status),
            current_step=model.current_step,
            steps=list(model.steps or []),
            results=dict(model.results or {}),
            errors=dict(model.errors or {}),
            started_at=model.started_at,
            completed_at=model.completed_at,
        )

    @staticmethod
    def _update_model(model: WorkflowExecutionModel, execution: WorkflowExecution) -> None:
        model.workflow_id = execution.workflow_id
        model.status = execution.status.value
        model.current_step = execution.current_step
        model.steps = [dict(s) if isinstance(s, dict) else s for s in execution.steps]
        model.results = dict(execution.results)
        model.errors = dict(execution.errors)
        model.started_at = execution.started_at
        model.completed_at = execution.completed_at
