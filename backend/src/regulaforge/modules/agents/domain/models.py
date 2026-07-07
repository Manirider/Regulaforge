from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED = "paused"
    DISABLED = "disabled"


@dataclass
class AgentConfig:
    max_iterations: int = 10
    timeout_seconds: int = 300
    temperature: float = 0.3
    model: str = "gpt-4"
    allow_delegation: bool = True
    max_concurrent_tasks: int = 5
    retry_on_failure: bool = True
    max_retries: int = 3
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class Agent:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    agent_type: str = "general"
    status: AgentStatus = AgentStatus.IDLE
    configuration: AgentConfig = field(default_factory=AgentConfig)
    capabilities: list[str] = field(default_factory=list)
    tenant_id: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentExecution:
    id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    task: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: Optional[dict[str, Any]] = None
    status: AgentStatus = AgentStatus.RUNNING
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)
    triggered_by: str = ""
