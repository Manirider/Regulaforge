from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4


@dataclass
class AuthEvent:
    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = ""
    user_id: str = ""
    email: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Optional[dict[str, Any]] = None


@dataclass
class UserLoggedIn(AuthEvent):
    event_type: str = "user.logged_in"


@dataclass
class UserLoggedOut(AuthEvent):
    event_type: str = "user.logged_out"


@dataclass
class UserRegistered(AuthEvent):
    event_type: str = "user.registered"


@dataclass
class TokenRefreshed(AuthEvent):
    event_type: str = "token.refreshed"


@dataclass
class PasswordReset(AuthEvent):
    event_type: str = "password.reset"


@dataclass
class LoginFailed(AuthEvent):
    event_type: str = "login.failed"
    reason: str = ""
