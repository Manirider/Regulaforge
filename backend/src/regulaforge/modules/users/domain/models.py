from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"
    DELETED = "deleted"


@dataclass
class UserProfile:
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    avatar_url: str = ""
    department: str = ""
    title: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class User:
    id: str = field(default_factory=lambda: str(uuid4()))
    email: str = ""
    username: str = ""
    hashed_password: str = ""
    status: UserStatus = UserStatus.PENDING_VERIFICATION
    profile: UserProfile = field(default_factory=UserProfile)
    tenant_id: str = ""
    mfa_enabled: bool = False
    mfa_secret: str = ""
    last_login_at: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
