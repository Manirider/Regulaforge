from enum import Enum


class AgentRole(str, Enum):
    SUPERVISOR = "supervisor"
    MONITORING = "monitoring"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    RISK_PREDICTION = "risk_prediction"
    CLAUSE_DRAFTING = "clause_drafting"
    LEGAL = "legal"
    AUDIT = "audit"
    NOTIFICATION = "notification"
    HUMAN_APPROVAL = "human_approval"


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class RoutingDecision(str, Enum):
    ROUTE_TO_SUPERVISOR = "route_to_supervisor"
    ROUTE_TO_MONITORING = "route_to_monitoring"
    ROUTE_TO_KNOWLEDGE_GRAPH = "route_to_knowledge_graph"
    ROUTE_TO_RISK_PREDICTION = "route_to_risk_prediction"
    ROUTE_TO_CLAUSE_DRAFTING = "route_to_clause_drafting"
    ROUTE_TO_LEGAL = "route_to_legal"
    ROUTE_TO_AUDIT = "route_to_audit"
    ROUTE_TO_NOTIFICATION = "route_to_notification"
    ROUTE_TO_HUMAN_APPROVAL = "route_to_human_approval"
    COMPLETE = "complete"
    ESCALATE = "escalate"
    FAIL = "fail"
