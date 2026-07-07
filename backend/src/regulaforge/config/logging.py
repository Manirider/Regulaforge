"""Enterprise logging configuration.

Provides structured JSON logging with context propagation,
correlation IDs, and integration with OpenTelemetry for distributed tracing.
Supports log aggregation systems like ELK, Datadog, and Splunk.
"""

from __future__ import annotations

import dataclasses
import logging
import logging.config
import sys
import traceback
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel
from pythonjsonlogger import jsonlogger

from regulaforge.config.settings import settings


# ─── Context variable for correlation ID (async-safe) ───────────────────

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

SENSITIVE_FIELD_NAMES = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "api_secret",
    "access_key",
    "private_key",
    "authorization",
    "auth",
    "ssn",
    "credit_card",
    "card_number",
    "cvv",
    "cvv2",
    "pin",
    "phone",
    "email",
}

import re as _re

_SENSITIVE_REGEX: list[tuple[_re.Pattern[str], str]] = [
    (_re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "***-**-****"),                     # SSN
    (_re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "****-****-****-****"),           # credit card
    (_re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "***@***.***"),  # email
    (_re.compile(r"\b\+?1?\d{10,15}\b"), "***-***-****"),                       # phone
    (_re.compile(r"Bearer\s+[A-Za-z0-9._-]+", _re.IGNORECASE), "Bearer ***"),   # Bearer token
    (_re.compile(r"JWT\s+[A-Za-z0-9._-]+", _re.IGNORECASE), "JWT ***"),         # JWT
]


@dataclasses.dataclass
class LogConfig:
    """Logging configuration overrides.

    Pass to ``configure_logging()`` to customize settings at runtime.
    ``None`` values defer to the global ``settings`` instance.
    """

    level: Optional[str] = None
    use_json: Optional[bool] = None
    correlation_id: Optional[str] = None


class CorrelationIdFilter(logging.Filter):
    """Adds/reads a correlation ID from a context variable (async-safe)."""

    @staticmethod
    def set_correlation_id(cid: Optional[str] = None) -> str:
        value = cid or str(uuid.uuid4())
        _correlation_id.set(value)
        return value

    @staticmethod
    def get_correlation_id() -> str:
        return _correlation_id.get()

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = self.get_correlation_id()
        return True


class SensitiveDataFilter(logging.Filter):
    """Masks sensitive data patterns from log messages and fields.

    Uses pre-compiled regex patterns for performance.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "args") and isinstance(record.args, dict):
            sanitized: dict[str, Any] = {}
            for key, value in record.args.items():
                sanitized[key] = "***" if key.lower() in SENSITIVE_FIELD_NAMES else value
            record.args = sanitized

        if hasattr(record, "msg") and isinstance(record.msg, str):
            msg: str = record.msg
            for pattern, replacement in _SENSITIVE_REGEX:
                msg = pattern.sub(replacement, msg)
            record.msg = msg

        return True


class StructuredLogRecord(BaseModel):
    """Pydantic model for structured log data.

    Use when you want type-safe, serializable extra fields in log records.
    Example::

        StructuredLogRecord(event="user.login", user_id="abc-123")
    """

    event: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with RegulaForge-specific fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno
        log_record["environment"] = settings.environment.value
        log_record["service"] = settings.app_name
        log_record["version"] = settings.app_version

        cid = _correlation_id.get()
        if cid:
            log_record["correlation_id"] = cid

        if record.exc_info and record.exc_info[0]:
            exc_type, exc_value, exc_tb = record.exc_info
            log_record["exception"] = {
                "type": exc_type.__name__,
                "message": str(exc_value),
                "traceback": (
                    "".join(traceback.format_tb(exc_tb)) if exc_tb else None
                ),
            }

        log_record.pop("exc_info", None)
        log_record.pop("exc_text", None)


def configure_logging(config: Optional[LogConfig] = None) -> None:
    """Configure application-wide logging with structured JSON output.

    Sets up:
    - JSON-formatted logs for production log aggregation
    - Correlation ID propagation (async-safe via ``contextvars``)
    - Sensitive data masking
    - Environment-specific log levels
    """
    cfg = config or LogConfig()
    log_level = cfg.level or settings.log_level.value
    use_json = cfg.use_json if cfg.use_json is not None else settings.log_json

    if cfg.correlation_id:
        CorrelationIdFilter.set_correlation_id(cfg.correlation_id)

    base_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "correlation_id": {
                "()": CorrelationIdFilter,
            },
            "sensitive_data": {
                "()": SensitiveDataFilter,
            },
        },
        "formatters": {
            "json": {
                "()": CustomJsonFormatter,
                "format": (
                    "%(message)s %(level)s %(name)s "
                    "%(module)s %(funcName)s"
                ),
            },
            "standard": {
                "format": (
                    "[%(asctime)s] %(levelname)-8s | %(correlation_id)s | "
                    "%(name)s:%(funcName)s:%(lineno)d | %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "json" if use_json else "standard",
                "filters": ["correlation_id", "sensitive_data"],
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "regulaforge": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "WARNING" if settings.is_production() else "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "WARNING" if settings.is_production() else "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "aiormq": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"],
        },
    }

    logging.config.dictConfig(base_config)

    if settings.is_development():
        for noisy in ("httpx", "httpcore", "asyncio"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(
    name: str,
    extra_fields: Optional[dict[str, Any]] = None,
) -> logging.Logger:
    """Get a configured logger instance for the given module name.

    Args:
        name: The module or component name (typically ``__name__``).
        extra_fields: Optional static fields to include in every log call.

    Returns:
        A configured Logger instance.
    """
    logger = logging.getLogger(f"regulaforge.{name}")
    if extra_fields:
        logger = logging.LoggerAdapter(logger, extra_fields)
    return logger


__all__ = [
    "configure_logging",
    "get_logger",
    "CorrelationIdFilter",
    "SensitiveDataFilter",
    "StructuredLogRecord",
    "LogConfig",
]
