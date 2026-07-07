from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class SettingCategory(str, Enum):
    GENERAL = "general"
    SECURITY = "security"
    NOTIFICATIONS = "notifications"
    INTEGRATIONS = "integrations"
    AI = "ai"
    COMPLIANCE = "compliance"
    WORKFLOW = "workflow"
    TENANT = "tenant"


@dataclass
class Setting:
    id: str = field(default_factory=lambda: str(uuid4()))
    key: str = ""
    value: Any = ""
    category: SettingCategory = SettingCategory.GENERAL
    description: str = ""
    value_type: str = "string"
    is_sensitive: bool = False
    is_tenant_level: bool = False
    is_public: bool = False
    validation_rules: dict[str, Any] = field(default_factory=dict)
    tenant_id: str = ""
    updated_by: str = ""
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
