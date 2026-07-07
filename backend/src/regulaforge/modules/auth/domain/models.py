from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    RESET_PASSWORD = "reset_password"
    EMAIL_VERIFY = "email_verify"


@dataclass
class AuthToken:
    token: str
    token_type: TokenType
    expires_at: datetime
    issued_at: datetime = field(default_factory=datetime.utcnow)
    jti: str = field(default_factory=lambda: str(uuid4()))
    revoked: bool = False


@dataclass
class LoginRequest:
    email: str
    password: str
    tenant_id: Optional[str] = None
    remember_me: bool = False


@dataclass
class RegisterRequest:
    email: str
    password: str
    full_name: str
    tenant_id: Optional[str] = None
    invite_token: Optional[str] = None


@dataclass
class LoginResponse:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user_id: str = ""
    email: str = ""
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)


@dataclass
class RefreshRequest:
    refresh_token: str
