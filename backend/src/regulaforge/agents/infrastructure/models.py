"""SQLAlchemy ORM models for the Multi-Agent AI System.

Provides persistent storage for agent tasks, workflow executions,
and workflow definitions with proper indexing for common query patterns.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON as SA_JSON
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from regulaforge.infrastructure.persistence.database import Base
from regulaforge.infrastructure.persistence.models.base import GUID, TimestampMixin


class AgentTaskModel(TimestampMixin, Base):
    """ORM model for agent task persistence.

    Stores task lifecycle data including input/output payloads,
    execution metadata, and error information.
    """

    __tablename__ = "agent_tasks"

    id: Mapped[GUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
        comment="Unique task identifier",
    )
    agent_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="The type of agent assigned to this task",
    )
    task_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        comment="The type of task to execute",
    )
    input_data: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=False,
        default=dict,
        comment="Task input payload",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        comment="Task priority (1-10, higher is more important)",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        index=True,
        comment="Current task status (pending, assigned, in_progress, completed, failed, cancelled, retrying)",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task execution started (UTC)",
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task execution completed (UTC)",
    )
    error: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if task failed",
    )
    output_data: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=True,
        default=None,
        comment="Task output payload on success",
    )
    correlation_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        index=True,
        comment="Correlation ID for workflow tracing",
    )

    def __repr__(self) -> str:
        return (
            f"<AgentTaskModel id={self.id} agent={self.agent_type} "
            f"type={self.task_type} status={self.status}>"
        )


class WorkflowExecutionModel(TimestampMixin, Base):
    """ORM model for workflow execution persistence.

    Tracks the runtime state of workflow executions including
    current step, accumulated results, and error information.
    """

    __tablename__ = "workflow_executions"

    id: Mapped[GUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
        comment="Unique execution identifier",
    )
    workflow_id: Mapped[GUID] = mapped_column(
        GUID,
        nullable=False,
        index=True,
        comment="Reference to the workflow definition",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        index=True,
        comment="Current execution status",
    )
    current_step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Index of the currently executing step",
    )
    steps: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=False,
        default=list,
        comment="List of step configurations",
    )
    results: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=False,
        default=dict,
        comment="Accumulated results keyed by step index",
    )
    errors: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=False,
        default=dict,
        comment="Errors keyed by step index",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When execution started (UTC)",
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When execution completed (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowExecutionModel id={self.id} "
            f"workflow={self.workflow_id} status={self.status}>"
        )


class WorkflowDefinitionModel(TimestampMixin, Base):
    """ORM model for workflow definition persistence.

    Stores named workflow definitions with their step configurations,
    timeout settings, and retry policies.
    """

    __tablename__ = "workflow_definitions"

    id: Mapped[GUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid4,
        comment="Unique workflow definition identifier",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique workflow name",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Workflow description and purpose",
    )
    steps: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=False,
        default=list,
        comment="List of workflow step configurations",
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3600,
        comment="Maximum workflow execution time",
    )
    retry_policy: Mapped[dict] = mapped_column(
        SA_JSON,
        nullable=True,
        default=dict,
        comment="Retry policy configuration",
    )

    def __repr__(self) -> str:
        return f"<WorkflowDefinitionModel id={self.id} name={self.name}>"
