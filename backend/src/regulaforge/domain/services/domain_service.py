"""Base class for all domain services."""

import logging
from abc import ABC
from typing import Any, Optional

from regulaforge.common.exceptions import ValidationError
from regulaforge.config.logging import get_logger


class DomainService(ABC):
    """Abstract base for all domain services.

    Provides logging, invariant checking, and standardized validation error raising.
    """

    def __init__(self) -> None:
        self._logger = get_logger(self.__class__.__name__)

    @property
    def logger(self) -> logging.Logger:
        """The logger instance configured for this domain service."""
        return self._logger

    def _check_invariant(self, condition: bool, message: str, code: str = "INVARIANT_VIOLATION") -> None:
        """Assert a domain invariant.

        Args:
            condition: The condition that must be True.
            message: The error message if the condition is False.
            code: The error code for classification.

        Raises:
            ValidationError: If the invariant condition is violated.
        """
        if not condition:
            self._raise_domain_error(message, code)

    def _raise_domain_error(self, message: str, code: str = "DOMAIN_ERROR") -> None:
        """Raise a standardized domain error (as a ValidationError).

        Args:
            message: The error message.
            code: The classification code.

        Raises:
            ValidationError: Always raised with the provided message and code.
        """
        raise ValidationError(
            message=message,
            code=code,
            status_code=400,  # Bad Request for domain-level rule violations
        )
