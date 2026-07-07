from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from regulaforge.agents.domain.enums import (
    AgentRole,
    AgentStatus,
    RoutingDecision,
    TaskPriority,
    TaskStatus,
)


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    function: Optional[Callable[..., Any]] = None


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReasoningStep:
    step_number: int
    description: str
    input: Optional[str] = None
    output: Optional[str] = None
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0


@dataclass
class ConfidenceScore:
    overall: float = 0.0
    accuracy: float = 0.0
    completeness: float = 0.0
    relevance: float = 0.0
    reasoning_quality: float = 0.0


@dataclass
class EvaluationResult:
    passed: bool = False
    score: ConfidenceScore = field(default_factory=ConfidenceScore)
    feedback: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class AgentMemory:
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    short_term: dict[str, Any] = field(default_factory=dict)
    long_term: dict[str, Any] = field(default_factory=dict)
    task_history: list[str] = field(default_factory=list)
    max_history: int = 100

    def add_interaction(self, role: str, content: str, metadata: Optional[dict[str, Any]] = None) -> None:
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        })
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

    def store(self, key: str, value: Any, persistent: bool = False) -> None:
        if persistent:
            self.long_term[key] = value
        else:
            self.short_term[key] = value

    def recall(self, key: str, default: Any = None) -> Any:
        return self.short_term.get(key, self.long_term.get(key, default))

    def clear_short_term(self) -> None:
        self.short_term.clear()


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[AgentRole] = None
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    parent_task_id: Optional[str] = None
    subtask_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class AgentState:
    agent_id: str = ""
    role: AgentRole = AgentRole.SUPERVISOR
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[Task] = None
    task_queue: list[Task] = field(default_factory=list)
    memory: AgentMemory = field(default_factory=AgentMemory)
    confidence: ConfidenceScore = field(default_factory=ConfidenceScore)
    reasoning_trace: list[ReasoningStep] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    evaluation: EvaluationResult = field(default_factory=EvaluationResult)
    routing_decision: Optional[RoutingDecision] = None
    error_count: int = 0
    max_retries: int = 3
    fallback_used: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
