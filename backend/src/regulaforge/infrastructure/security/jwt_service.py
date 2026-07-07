"""JWT token creation, decoding, and verification service.

Handles access and refresh token lifecycle using HS256/RS256
with proper claims validation and expiry management.

Refactored from a single 206-line class into focused collaborators:
- TokenConfig: configuration and validation
- TokenCreator: token creation (access + refresh)
- TokenVerifier: decoding, verification, expiry checks
- JWTService: backward-compatible facade
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)

_SUPPORTED_ALGORITHMS: frozenset[str] = frozenset({"HS256", "HS384", "HS512", "RS256"})


@dataclass(frozen=True)
class TokenConfig:
    """Immutable configuration for JWT token operations."""

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    def __post_init__(self) -> None:
        if hasattr(self.secret_key, "get_secret_value"):
            object.__setattr__(self, "secret_key", self.secret_key.get_secret_value())
        if not self.secret_key or len(self.secret_key) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")
        if self.algorithm not in _SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}. Supported: {sorted(_SUPPORTED_ALGORITHMS)}")

    @classmethod
    def from_settings(cls) -> "TokenConfig":
        """Create config from application settings."""
        return cls(
            secret_key=settings.security.secret_key,
            algorithm=settings.security.algorithm,
            access_token_expire_minutes=settings.security.access_token_expire_minutes,
            refresh_token_expire_days=settings.security.refresh_token_expire_days,
        )


class TokenCreator:
    """Creates signed JWT access and refresh tokens."""

    def __init__(self, config: TokenConfig) -> None:
        self._config = config
        self._access_expire = timedelta(minutes=config.access_token_expire_minutes)
        self._refresh_expire = timedelta(days=config.refresh_token_expire_days)

    def create_access_token(
        self,
        subject: str,
        tenant_id: Optional[str] = None,
        roles: Optional[list[str]] = None,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a short-lived access token."""
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": subject,
            "exp": now + self._access_expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "token_type": "access",
        }
        if tenant_id:
            payload["tenant_id"] = tenant_id
        if roles:
            payload["roles"] = roles
        if additional_claims:
            payload.update(additional_claims)
        try:
            return jwt.encode(payload, self._config.secret_key, algorithm=self._config.algorithm)
        except Exception as e:
            logger.error("Failed to create access token: %s", e)
            raise ValueError("Failed to create access token") from e

    def create_refresh_token(
        self,
        subject: str,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a long-lived refresh token."""
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": subject,
            "exp": now + self._refresh_expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "token_type": "refresh",
        }
        if additional_claims:
            payload.update(additional_claims)
        try:
            return jwt.encode(payload, self._config.secret_key, algorithm=self._config.algorithm)
        except Exception as e:
            logger.error("Failed to create refresh token: %s", e)
            raise ValueError("Failed to create refresh token") from e


class TokenVerifier:
    """Verifies, decodes, and inspects JWT tokens."""

    def __init__(self, config: TokenConfig) -> None:
        self._config = config

    def decode_token(self, token: str, verify: bool = True) -> dict[str, Any]:
        """Decode a JWT token, optionally verifying signature and expiry."""
        options = {"verify_exp": verify, "verify_signature": verify}
        try:
            return jwt.decode(
                token,
                self._config.secret_key,
                algorithms=[self._config.algorithm],
                options=options,
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token: %s", e)
            raise

    def verify_token(self, token: str, expected_type: Optional[str] = None) -> dict[str, Any]:
        """Verify a token's signature, expiry, and optional type claim."""
        payload = self.decode_token(token, verify=True)
        if expected_type and payload.get("token_type") != expected_type:
            raise ValueError(
                f"Invalid token type: expected '{expected_type}', "
                f"got '{payload.get('token_type')}'"
            )
        return payload

    def get_subject(self, token: str) -> str:
        """Extract the subject claim without verification."""
        return self.decode_token(token, verify=False)["sub"]

    def is_token_expired(self, token: str) -> bool:
        """Check if a token has expired without raising exceptions."""
        try:
            self.decode_token(token, verify=True)
            return False
        except jwt.ExpiredSignatureError:
            return True
        except jwt.InvalidTokenError:
            return True


class JWTService:
    """Backward-compatible facade for JWT token operations.

    Delegates to TokenConfig, TokenCreator, and TokenVerifier.
    New code should use the focused classes directly.
    """

    def __init__(
        self,
        secret_key: str = settings.security.secret_key,
        algorithm: str = settings.security.algorithm,
        access_token_expire_minutes: int = settings.security.access_token_expire_minutes,
        refresh_token_expire_days: int = settings.security.refresh_token_expire_days,
    ) -> None:
        config = TokenConfig(
            secret_key=secret_key,
            algorithm=algorithm,
            access_token_expire_minutes=access_token_expire_minutes,
            refresh_token_expire_days=refresh_token_expire_days,
        )
        self._creator = TokenCreator(config)
        self._verifier = TokenVerifier(config)

    def create_access_token(
        self,
        subject: str,
        tenant_id: Optional[str] = None,
        roles: Optional[list[str]] = None,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        return self._creator.create_access_token(
            subject=subject,
            tenant_id=tenant_id,
            roles=roles,
            additional_claims=additional_claims,
        )

    def create_refresh_token(
        self,
        subject: str,
        additional_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        return self._creator.create_refresh_token(
            subject=subject,
            additional_claims=additional_claims,
        )

    def decode_token(self, token: str, verify: bool = True) -> dict[str, Any]:
        return self._verifier.decode_token(token, verify=verify)

    def verify_token(self, token: str, expected_type: Optional[str] = None) -> dict[str, Any]:
        return self._verifier.verify_token(token, expected_type=expected_type)

    def get_subject(self, token: str) -> str:
        return self._verifier.get_subject(token)

    def is_token_expired(self, token: str) -> bool:
        return self._verifier.is_token_expired(token)
