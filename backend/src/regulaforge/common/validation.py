"""Reusable validation utilities and Pydantic field types."""

from __future__ import annotations

import re
from typing import (
    Annotated,
    Any,
    AsyncIterator,
    List,
    Optional,
    Protocol,
    Sequence,
    Union,
)

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
)


# ─── Constrained string types ────────────────────────────────────────────

PhoneNumber = Annotated[
    str,
    StringConstraints(
        min_length=8,
        max_length=20,
        pattern=r"^\+?[1-9]\d{7,19}$",
    ),
]
"""E.164 phone number (e.g. ``+14155552671``)."""

CountryCode = Annotated[
    str,
    StringConstraints(
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
    ),
]
"""ISO 3166-1 alpha-2 country code (e.g. ``US``)."""

NonEmptyStr = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
]

HexColor = Annotated[
    str,
    StringConstraints(
        pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$",
    ),
]

Slug = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
    ),
]

SemVer = Annotated[
    str,
    StringConstraints(
        pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$",
    ),
]


# ─── Password validation ─────────────────────────────────────────────────

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def validate_password_strength(password: str) -> str:
    """Validate password strength with enterprise-grade policy.

    Rules:
        - Minimum 12 characters
        - Maximum 128 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must not exceed {PASSWORD_MAX_LENGTH} characters"
        )
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-~`+=\[\]\\;/\']', password):
        raise ValueError("Password must contain at least one special character")
    return password


StrongPassword = Annotated[str, AfterValidator(validate_password_strength)]


# ─── URL validation ──────────────────────────────────────────────────────

def validate_url(value: str) -> str:
    """Validate a URL with proper scheme and structure."""
    url_pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    if not url_pattern.match(value):
        raise ValueError(f"Invalid URL: {value}")
    return value


UrlString = Annotated[str, AfterValidator(validate_url)]


# ─── File validation ─────────────────────────────────────────────────────

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "application/json",
}
ALLOWED_ML_TYPES = {
    "application/x-hdf5",
    "application/octet-stream",
    "application/xml",
    "text/csv",
    "application/json",
}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


class FileValidationProtocol(Protocol):
    """Protocol for file-like objects that can be validated."""

    @property
    def filename(self) -> str:
        ...

    @property
    def content_type(self) -> str:
        ...

    @property
    def size(self) -> int:
        """File size in bytes. May return 0 if unknown."""
        ...

    async def read(self) -> bytes:
        ...


async def verify_file_type(
    file: FileValidationProtocol,
    allowed_types: set[str],
    max_size: int = MAX_FILE_SIZE,
) -> bool:
    """Verify a file's content type and size constraints.

    Checks ``content_type`` and ``size`` properties before reading content.
    Raises ``ValueError`` if checks fail.
    """
    if file.content_type not in allowed_types:
        raise ValueError(
            f"File type '{file.content_type}' not allowed. "
            f"Allowed types: {', '.join(sorted(allowed_types))}"
        )
    if file.size > max_size:
        raise ValueError(
            f"File size {file.size} exceeds maximum {max_size} bytes"
        )
    return True


# ─── Pagination & Sorting models ─────────────────────────────────────────

class PaginationParams(BaseModel):
    """Standard pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    size: int = Field(default=20, ge=1, le=100, description="Items per page")


class SortParams(BaseModel):
    """Standard sorting query parameters."""

    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    order: str = Field(default="asc", pattern=r"^(asc|desc)$", description="Sort order")


# ─── Range and bounded types ─────────────────────────────────────────────

class Probability(float):
    """A float in the [0.0, 1.0] range."""

    def __new__(cls, value: float) -> Probability:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Probability must be between 0.0 and 1.0, got {value}")
        return super().__new__(cls, value)


class ConfidenceScore(float):
    """A float in the [0.0, 1.0] range representing model confidence."""

    def __new__(cls, value: float) -> ConfidenceScore:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {value}")
        return super().__new__(cls, value)


Percentage = Annotated[float, Field(ge=0.0, le=100.0)]


# ─── Generic validation helpers ──────────────────────────────────────────

def non_empty(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("Value must not be empty")
    return value


def positive_int(value: int) -> int:
    if value <= 0:
        raise ValueError(f"Value must be positive, got {value}")
    return value


NonEmptyString = Annotated[str, AfterValidator(non_empty)]
PositiveInt = Annotated[int, AfterValidator(positive_int)]


__all__ = [
    "PhoneNumber",
    "CountryCode",
    "NonEmptyStr",
    "HexColor",
    "Slug",
    "SemVer",
    "PASSWORD_MIN_LENGTH",
    "PASSWORD_MAX_LENGTH",
    "validate_password_strength",
    "StrongPassword",
    "validate_url",
    "UrlString",
    "ALLOWED_IMAGE_TYPES",
    "ALLOWED_DOCUMENT_TYPES",
    "ALLOWED_ML_TYPES",
    "MAX_FILE_SIZE",
    "verify_file_type",
    "PaginationParams",
    "SortParams",
    "Probability",
    "ConfidenceScore",
    "Percentage",
    "non_empty",
    "positive_int",
    "NonEmptyString",
    "PositiveInt",
]
