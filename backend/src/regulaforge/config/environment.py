"""Centralized environment management.

Provides runtime environment detection, environment-specific configuration
loading, feature flag support, and process metadata. Thread-safe singleton
that complements ``settings.py`` with operational introspection.

Usage::

    from regulaforge.config.environment import env_manager

    if env_manager.is_production:
        ...

    if env_manager.is_feature_enabled("graphrag_v2"):
        ...
"""

from __future__ import annotations

import os
import platform
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Final, Optional


class Environment(str, Enum):
    """Deployment environment identifiers."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


# ─── Feature flag defaults ────────────────────────────────────────────────

_DEFAULT_FEATURE_FLAGS: dict[str, bool] = {
    "graphrag_v2": False,
    "xai_explanations": False,
    "realtime_websocket": False,
    "ml_risk_predictions": False,
    "advanced_audit": False,
}

_ENV_VAR_NAME: Final[str] = "REGULAFORGE_ENVIRONMENT"
_FEATURE_FLAG_PREFIX: Final[str] = "REGULAFORGE_FEATURE_"


class EnvironmentManager:
    """Thread-safe environment manager singleton.

    Detects the current environment, loads environment-specific ``.env``
    files, manages feature flags, and exposes process metadata.

    This class is instantiated once at module level. Access via::

        from regulaforge.config.environment import env_manager
    """

    _instance: Optional[EnvironmentManager] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> EnvironmentManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._start_time = time.monotonic()
        self._start_utc = datetime.now(timezone.utc)
        self._environment = self._detect_environment()
        self._feature_flags: dict[str, bool] = dict(_DEFAULT_FEATURE_FLAGS)
        self._metadata: dict[str, Any] = {}

        self._load_env_file()
        self._load_feature_flags()
        self._collect_metadata()

    # ─── Environment detection ──────────────────────────────────────────

    @staticmethod
    def _detect_environment() -> Environment:
        """Detect environment from env var, defaulting to development."""
        raw = os.getenv(_ENV_VAR_NAME, "development").lower().strip()
        try:
            return Environment(raw)
        except ValueError:
            return Environment.DEVELOPMENT

    def _load_env_file(self) -> None:
        """Load environment-specific .env file if it exists.

        Searches for ``.env.<environment>`` in the project root
        (two levels up from this file, or from CWD).
        """
        try:
            from dotenv import load_dotenv
        except ImportError:
            return

        # Try project root (backend/) then CWD
        search_dirs = [
            Path(__file__).resolve().parent.parent.parent.parent,  # backend/
            Path.cwd(),
        ]

        env_filename = f".env.{self._environment.value}"
        for search_dir in search_dirs:
            env_path = search_dir / env_filename
            if env_path.exists():
                load_dotenv(env_path, override=False)
                return

    def _load_feature_flags(self) -> None:
        """Load feature flags from environment variables.

        Env var format: ``REGULAFORGE_FEATURE_<FLAG_NAME>=true|false``
        """
        for flag_name in self._feature_flags:
            env_key = f"{_FEATURE_FLAG_PREFIX}{flag_name.upper()}"
            raw = os.getenv(env_key)
            if raw is not None:
                self._feature_flags[flag_name] = raw.lower().strip() in {
                    "true", "1", "yes", "on",
                }

    def _collect_metadata(self) -> None:
        """Collect process and platform metadata."""
        self._metadata = {
            "hostname": platform.node(),
            "pid": os.getpid(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "start_utc": self._start_utc.isoformat(),
        }

    # ─── Public API ─────────────────────────────────────────────────────

    @property
    def current(self) -> Environment:
        """Current deployment environment."""
        return self._environment

    @property
    def name(self) -> str:
        """Environment name as lowercase string."""
        return self._environment.value

    @property
    def is_development(self) -> bool:
        return self._environment == Environment.DEVELOPMENT

    @property
    def is_staging(self) -> bool:
        return self._environment == Environment.STAGING

    @property
    def is_production(self) -> bool:
        return self._environment == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        return self._environment == Environment.TESTING

    @property
    def is_local(self) -> bool:
        """True for development or testing (non-deployed environments)."""
        return self._environment in {Environment.DEVELOPMENT, Environment.TESTING}

    @property
    def is_deployed(self) -> bool:
        """True for staging or production (deployed environments)."""
        return self._environment in {Environment.STAGING, Environment.PRODUCTION}

    @property
    def uptime_seconds(self) -> float:
        """Process uptime in seconds since manager initialization."""
        return time.monotonic() - self._start_time

    @property
    def metadata(self) -> dict[str, Any]:
        """Process and platform metadata (read-only copy)."""
        return {
            **self._metadata,
            "environment": self._environment.value,
            "uptime_seconds": round(self.uptime_seconds, 2),
        }

    # ─── Feature flags ──────────────────────────────────────────────────

    def is_feature_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled.

        Args:
            flag_name: Feature flag identifier (e.g. ``"graphrag_v2"``).

        Returns:
            True if the flag is enabled, False if disabled or unknown.
        """
        return self._feature_flags.get(flag_name, False)

    def set_feature_flag(self, flag_name: str, enabled: bool) -> None:
        """Set a feature flag at runtime (for testing or admin API).

        Args:
            flag_name: Feature flag identifier.
            enabled: Whether the flag should be enabled.
        """
        self._feature_flags[flag_name] = enabled

    def get_all_feature_flags(self) -> dict[str, bool]:
        """Return a copy of all feature flags."""
        return dict(self._feature_flags)

    def register_feature_flag(
        self,
        flag_name: str,
        default: bool = False,
    ) -> None:
        """Register a new feature flag with a default value.

        Does not overwrite if already set (e.g. from env var).

        Args:
            flag_name: Feature flag identifier.
            default: Default value if not already configured.
        """
        if flag_name not in self._feature_flags:
            self._feature_flags[flag_name] = default
            # Check env override
            env_key = f"{_FEATURE_FLAG_PREFIX}{flag_name.upper()}"
            raw = os.getenv(env_key)
            if raw is not None:
                self._feature_flags[flag_name] = raw.lower().strip() in {
                    "true", "1", "yes", "on",
                }

    # ─── Require environment guards ─────────────────────────────────────

    def require(self, *environments: Environment) -> None:
        """Assert the current environment is one of the given values.

        Raises:
            RuntimeError: If the current environment is not in the allowed set.
        """
        if self._environment not in environments:
            allowed = ", ".join(e.value for e in environments)
            raise RuntimeError(
                f"Operation requires environment(s): {allowed}. "
                f"Current: {self._environment.value}"
            )

    def __repr__(self) -> str:
        flags_on = sum(1 for v in self._feature_flags.values() if v)
        return (
            f"EnvironmentManager("
            f"env={self._environment.value}, "
            f"features={flags_on}/{len(self._feature_flags)} enabled)"
        )


# ─── Module-level singleton ──────────────────────────────────────────────

env_manager = EnvironmentManager()
"""Global environment manager singleton."""


__all__ = [
    "Environment",
    "EnvironmentManager",
    "env_manager",
]
