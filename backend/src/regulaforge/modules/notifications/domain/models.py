from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"
    SLACK = "slack"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class NotificationTemplate:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    subject: str = ""
    body: str = ""
    channel: NotificationChannel = NotificationChannel.IN_APP
    variables: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NotificationPreference:
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    channel: NotificationChannel = NotificationChannel.IN_APP
    enabled: bool = True
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    digest_frequency: str = "instant"


@dataclass
class Notification:
    id: str = field(default_factory=lambda: str(uuid4()))
    recipient_id: str = ""
    recipient_email: str = ""
    channel: NotificationChannel = NotificationChannel.IN_APP
    title: str = ""
    body: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.PENDING
    template_id: str = ""
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    tenant_id: str = ""
