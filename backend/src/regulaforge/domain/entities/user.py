"""User entity - the identity and security aggregate root.

Represents a platform user with authentication state, multi-tenant
association, and account security features including lockout.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from regulaforge.config.constants import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PASSWORD_REQUIRE_DIGIT,
    PASSWORD_REQUIRE_LOWERCASE,
    PASSWORD_REQUIRE_SPECIAL,
    PASSWORD_REQUIRE_UPPERCASE,
)
from regulaforge.domain.entities.base import DomainEntity

MAX_FAILED_ATTEMPTS: int = 5
LOCKOUT_DURATION_MINUTES: int = 30
EMAIL_REGEX: re.Pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class User(DomainEntity):
    """A platform user with authentication and authorization state.

    This is an aggregate root for the identity and access subdomain.
    Manages password policies, account lockout, and login tracking.
    """

    def __init__(
        self,
        email: str,
        username: str,
        password_hash: Optional[str] = None,
        full_name: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
        is_active: bool = True,
        is_superuser: bool = False,
        last_login_at: Optional[datetime] = None,
        failed_login_attempts: int = 0,
        locked_until: Optional[datetime] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._validate_email(email)
        self._validate_username(username)

        self._email: str = email.lower().strip()
        self._username: str = username.strip()
        self._password_hash: Optional[str] = password_hash
        self._full_name: Optional[str] = full_name.strip() if full_name else None
        self._tenant_id: Optional[UUID] = tenant_id
        self._is_active: bool = is_active
        self._is_superuser: bool = is_superuser
        self._last_login_at: Optional[datetime] = last_login_at
        self._failed_login_attempts: int = failed_login_attempts
        self._locked_until: Optional[datetime] = locked_until

    @staticmethod
    def _validate_email(email: str) -> None:
        """Validate email format."""
        if not email or not EMAIL_REGEX.match(email.strip()):
            raise ValueError("Invalid email format")
        if len(email) > 254:
            raise ValueError("Email must not exceed 254 characters")

    @staticmethod
    def _validate_username(username: str) -> None:
        """Validate username format."""
        if not username or len(username.strip()) < 2:
            raise ValueError("Username must be at least 2 characters")
        if len(username) > 150:
            raise ValueError("Username must not exceed 150 characters")

    @staticmethod
    def validate_password(password: str) -> None:
        """Validate password against platform policy.

        Args:
            password: The plain-text password to validate.

        Raises:
            ValueError: If the password does not meet policy requirements.
        """
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        if len(password) > MAX_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must not exceed {MAX_PASSWORD_LENGTH} characters"
            )
        if PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter")
        if PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")
        if PASSWORD_REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'`~/]", password):
            raise ValueError("Password must contain at least one special character")

    @property
    def email(self) -> str:
        return self._email

    @property
    def username(self) -> str:
        return self._username

    @property
    def password_hash(self) -> Optional[str]:
        return self._password_hash

    @property
    def full_name(self) -> Optional[str]:
        return self._full_name

    @property
    def tenant_id(self) -> Optional[UUID]:
        return self._tenant_id

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_superuser(self) -> bool:
        return self._is_superuser

    @property
    def last_login_at(self) -> Optional[datetime]:
        return self._last_login_at

    @property
    def failed_login_attempts(self) -> int:
        return self._failed_login_attempts

    @property
    def locked_until(self) -> Optional[datetime]:
        return self._locked_until

    @property
    def is_locked(self) -> bool:
        """Check if the account is currently locked."""
        if self._locked_until is None:
            return False
        return datetime.now(timezone.utc) < self._locked_until

    def set_password_hash(self, password_hash: str, by: Optional[UUID] = None) -> None:
        """Update the password hash and fire a password changed event."""
        if not password_hash:
            raise ValueError("Password hash must not be empty")
        self._password_hash = password_hash
        self.mark_updated(by)

        from regulaforge.domain.events.user import UserPasswordChanged

        self.register_event(UserPasswordChanged(
            user_id=self._id,
            email=self._email,
        ))

    def record_login(self, by: Optional[UUID] = None) -> None:
        """Record a successful login and reset failed attempts."""
        self._last_login_at = datetime.now(timezone.utc)
        self._failed_login_attempts = 0
        self._locked_until = None
        self.mark_updated(by)

        from regulaforge.domain.events.user import UserLoggedIn

        self.register_event(UserLoggedIn(
            user_id=self._id,
            email=self._email,
        ))

    def record_failed_attempt(self, by: Optional[UUID] = None) -> None:
        """Record a failed login attempt and lock if threshold exceeded."""
        self._failed_login_attempts += 1
        if self._failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            self._locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=LOCKOUT_DURATION_MINUTES
            )
            self.mark_updated(by)

            from regulaforge.domain.events.user import UserLocked

            self.register_event(UserLocked(
                user_id=self._id,
                email=self._email,
                failed_attempts=self._failed_login_attempts,
                locked_until=self._locked_until,
            ))
        else:
            self.mark_updated(by)

    def lock(self, by: Optional[UUID] = None) -> None:
        """Manually lock the user account."""
        self._locked_until = datetime.now(timezone.utc) + timedelta(
            minutes=LOCKOUT_DURATION_MINUTES
        )
        self.mark_updated(by)

        from regulaforge.domain.events.user import UserLocked

        self.register_event(UserLocked(
            user_id=self._id,
            email=self._email,
            failed_attempts=self._failed_login_attempts,
            locked_until=self._locked_until,
        ))

    def unlock(self, by: Optional[UUID] = None) -> None:
        """Manually unlock the user account."""
        self._locked_until = None
        self._failed_login_attempts = 0
        self.mark_updated(by)

    def activate(self, by: Optional[UUID] = None) -> None:
        """Activate the user account."""
        self._is_active = True
        self.mark_updated(by)

    def deactivate(self, by: Optional[UUID] = None) -> None:
        """Deactivate the user account."""
        self._is_active = False
        self.mark_updated(by)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "email": self._email,
            "username": self._username,
            "full_name": self._full_name,
            "tenant_id": str(self._tenant_id) if self._tenant_id else None,
            "is_active": self._is_active,
            "is_superuser": self._is_superuser,
            "last_login_at": self._last_login_at.isoformat() if self._last_login_at else None,
            "failed_login_attempts": self._failed_login_attempts,
            "locked_until": self._locked_until.isoformat() if self._locked_until else None,
        })
        return base

    def __repr__(self) -> str:
        return f"<User {self._email}>"
