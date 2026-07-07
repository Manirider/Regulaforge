from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class Action(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"
    IMPORT = "import"
    ADMIN = "admin"


class Resource(str, Enum):
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    CONTRACT = "contract"
    REGULATION = "regulation"
    ASSESSMENT = "assessment"
    REPORT = "report"
    DOCUMENT = "document"
    ENTITY = "entity"
    SETTINGS = "settings"
    AUDIT_LOG = "audit_log"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    AGENT = "agent"
    NOTIFICATION = "notification"
    TENANT = "tenant"


@dataclass
class Permission:
    id: str = field(default_factory=lambda: str(uuid4()))
    resource: Resource = Resource.DOCUMENT
    action: Action = Action.READ
    conditions: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class Role:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    permissions: list[Permission] = field(default_factory=list)
    is_system: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RoleAssignment:
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    role_id: str = ""
    tenant_id: str = ""
    assigned_at: datetime = field(default_factory=datetime.utcnow)
    assigned_by: str = ""


@dataclass
class Policy:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    effect: str = "allow"
    resources: list[Resource] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
