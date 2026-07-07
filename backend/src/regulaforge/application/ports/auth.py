"""Authentication port interfaces (hexagonal architecture).

Defines the contracts for token management and password hashing
that the application layer depends on. Infrastructure implementations
inject concrete adapters behind these ports.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class TokenPayload:
    """Decoded token payload for use-case consumption.

    Carries the essential claims extracted from an access or
    refresh token without coupling the application layer to
    the JWT library or token format.
    """

    def __init__(
        self,
        subject: str,
        token_type: str,
        tenant_id: Optional[str] = None,
        roles: Optional[list[str]] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        self.subject = subject
        self.token_type = token_type
        self.tenant_id = tenant_id
        self.roles = roles or []
        self.extra = extra or {}


class IAuthTokenService(ABC):
    """Port for authentication token creation and verification.

    Implementations handle the full lifecycle of JWT (or any token
    format) including creation, decoding, and verification of
    access and refresh tokens.
    """

    @abstractmethod
    def create_access_token(
        self,
        subject: str,
        tenant_id: Optional[str] = None,
        roles: Optional[list[str]] = None,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a short-lived access token for the given subject.

        Args:
            subject: The user ID (or other principal identifier).
            tenant_id: Optional tenant for multi-tenant scoping.
            roles: Optional list of role names for authorization.
            additional_claims: Extra claims to embed in the token.

        Returns:
            A signed access token string.
        """
        ...

    @abstractmethod
    def create_refresh_token(
        self,
        subject: str,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a long-lived refresh token.

        Args:
            subject: The user ID (or other principal identifier).
            additional_claims: Extra claims to embed in the token.

        Returns:
            A signed refresh token string.
        """
        ...

    @abstractmethod
    def verify_token(self, token: str, expected_type: Optional[str] = None) -> TokenPayload:
        """Verify a token's signature, expiry, and optional type.

        Args:
            token: The token string to verify.
            expected_type: If provided, validates the token_type claim.

        Returns:
            A TokenPayload with decoded claims.

        Raises:
            ValueError: If the token is invalid, expired, or wrong type.
        """
        ...

    @abstractmethod
    def decode_token(self, token: str, verify: bool = True) -> TokenPayload:
        """Decode a token without verification (for introspection).

        Args:
            token: The token string to decode.
            verify: Whether to verify signature and expiry.

        Returns:
            A TokenPayload with decoded claims.

        Raises:
            ValueError: If the token is malformed or (if verify=True) invalid.
        """
        ...

    @abstractmethod
    def get_subject(self, token: str) -> str:
        """Extract the subject (user ID) from a token without verification.

        Args:
            token: The token string.

        Returns:
            The subject claim as a string.

        Raises:
            ValueError: If the token is malformed.
        """
        ...

    @abstractmethod
    def is_token_expired(self, token: str) -> bool:
        """Check whether a token has expired.

        Args:
            token: The token string to check.

        Returns:
            True if the token is expired or invalid, False otherwise.
        """
        ...


class IPasswordService(ABC):
    """Port for password hashing and verification.

    Implementations wrap a hashing algorithm (e.g., bcrypt, argon2)
    and provide secure password storage following current best
    practices.
    """

    @abstractmethod
    def hash_password(self, password: str) -> str:
        """Hash a plain-text password for secure storage.

        Args:
            password: The plain-text password (validated by caller).

        Returns:
            The hashed password string.

        Raises:
            ValueError: If the password is empty or exceeds max length.
        """
        ...

    @abstractmethod
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a plain-text password against a stored hash.

        Args:
            password: The plain-text password to check.
            password_hash: The stored hash to compare against.

        Returns:
            True if the password matches the hash, False otherwise.
        """
        ...

    @abstractmethod
    def is_hash_stale(self, password_hash: str) -> bool:
        """Check whether a password hash uses an outdated cost factor.

        Args:
            password_hash: The stored hash to evaluate.

        Returns:
            True if the hash should be re-computed with a higher cost.
        """
        ...
