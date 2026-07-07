"""Password hashing and verification service.

Uses bcrypt with configurable cost factor for secure
password storage following industry best practices.
"""

import bcrypt

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)


class PasswordService:
    """Provides password hashing and verification using bcrypt.

    The cost factor (bcrypt_rounds) is configured via application
    settings and can be increased over time as hardware improves.
    """

    def __init__(self, rounds: int = settings.security.bcrypt_rounds) -> None:
        if rounds < 4 or rounds > 20:
            raise ValueError("bcrypt rounds must be between 4 and 20")
        self._rounds = rounds

    @property
    def rounds(self) -> int:
        """The current bcrypt cost factor."""
        return self._rounds

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt with the configured cost factor.

        Args:
            password: The plain-text password to hash.

        Returns:
            The bcrypt hash string (includes salt and cost factor).

        Raises:
            ValueError: If the password is empty or too long.
        """
        if not password:
            raise ValueError("Password cannot be empty")
        if len(password) > 128:
            raise ValueError("Password must not exceed 128 characters")

        try:
            salt = bcrypt.gensalt(rounds=self._rounds)
            hashed: bytes = bcrypt.hashpw(
                password.encode("utf-8"), salt
            )
            return hashed.decode("utf-8")
        except Exception as e:
            logger.error("Password hashing failed: %s", e)
            raise ValueError("Failed to hash password") from e

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against a bcrypt hash.

        Args:
            password: The plain-text password to check.
            password_hash: The stored bcrypt hash to verify against.

        Returns:
            True if the password matches the hash, False otherwise.
        """
        if not password or not password_hash:
            return False

        try:
            result: bool = bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
            return result
        except (ValueError, TypeError) as e:
            logger.error("Password verification failed: %s", e)
            return False

    def is_hash_stale(self, password_hash: str) -> bool:
        """Check if a password hash uses an outdated cost factor.

        Args:
            password_hash: The stored bcrypt hash to check.

        Returns:
            True if the hash should be re-computed with a higher cost.
        """
        try:
            current_rounds = int(password_hash.split("$")[2].lstrip("0"))
            return current_rounds < self._rounds
        except (IndexError, ValueError):
            return True
