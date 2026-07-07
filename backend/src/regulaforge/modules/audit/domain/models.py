from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class AuditAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    APPROVE = "approve"
    REJECT = "reject"
    EXECUTE = "execute"
    DOWNLOAD = "download"
    ARCHIVE = "archive"
    RESTORE = "restore"


class AuditResource(str, Enum):
    USER = "user"
    CONTRACT = "contract"
    REGULATION = "regulation"
    DOCUMENT = "document"
    REPORT = "report"
    SETTINGS = "settings"
    ROLE = "role"
    PERMISSION = "permission"
    AGENT = "agent"
    NOTIFICATION = "notification"
    TEMPLATE = "template"
    ENTITY = "entity"
    ASSESSMENT = "assessment"
    TENANT = "tenant"


@dataclass
class AuditEntry:
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    actor_id: str = ""
    actor_email: str = ""
    action: AuditAction = AuditAction.READ
    resource: AuditResource = AuditResource.DOCUMENT
    resource_id: str = ""
    resource_name: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    tenant_id: str = ""
    changes: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
