"""User domain events."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.events.base import DomainEvent


class UserCreated(DomainEvent):
    """Emitted when a new user account is created."""

    def __init__(
        self,
        user_id: UUID,
        email: str,
        full_name: str,
        tenant_id: UUID,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="user.created",
            aggregate_id=user_id,
            aggregate_type="user",
            data={
                "email": email,
                "full_name": full_name,
                "tenant_id": str(tenant_id),
            },
            **kwargs,
        )


class UserLoggedIn(DomainEvent):
    """Emitted when a user successfully logs in."""

    def __init__(
        self,
        user_id: UUID,
        email: str,
        ip_address: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        data: dict = {"email": email}
        if ip_address:
            data["ip_address"] = ip_address
        super().__init__(
            event_type="user.logged_in",
            aggregate_id=user_id,
            aggregate_type="user",
            data=data,
            **kwargs,
        )


class UserLocked(DomainEvent):
    """Emitted when a user account is locked due to failed attempts."""

    def __init__(
        self,
        user_id: UUID,
        email: str,
        failed_attempts: int,
        locked_until: datetime,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="user.locked",
            aggregate_id=user_id,
            aggregate_type="user",
            data={
                "email": email,
                "failed_attempts": failed_attempts,
                "locked_until": locked_until.isoformat(),
            },
            **kwargs,
        )


class UserPasswordChanged(DomainEvent):
    """Emitted when a user changes their password."""

    def __init__(
        self,
        user_id: UUID,
        email: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            event_type="user.password_changed",
            aggregate_id=user_id,
            aggregate_type="user",
            data={"email": email},
            **kwargs,
        )
