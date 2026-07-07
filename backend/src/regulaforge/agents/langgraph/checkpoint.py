from __future__ import annotations

import logging
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

VALID_PERSISTENCE_TYPES = frozenset({"memory", "sqlite", "postgres"})


def create_checkpoint_saver(
    persistence_type: str = "memory",
    **kwargs: Any,
) -> BaseCheckpointSaver:
    normalized = persistence_type.strip().lower()
    if normalized not in VALID_PERSISTENCE_TYPES:
        logger.warning(
            "Unknown persistence type '%s'; falling back to memory. "
            "Valid types: %s",
            persistence_type,
            ", ".join(sorted(VALID_PERSISTENCE_TYPES)),
        )
        return MemorySaver()

    if normalized == "memory":
        logger.info("Using in-memory checkpoint saver")
        return MemorySaver()

    if normalized == "sqlite":
        return _create_sqlite_saver(**kwargs)

    return _create_postgres_saver(**kwargs)


def _create_sqlite_saver(**kwargs: Any) -> BaseCheckpointSaver:
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn_string = kwargs.get("conn_string", "checkpoints.db")
        if not isinstance(conn_string, str) or not conn_string.strip():
            conn_string = "checkpoints.db"
            logger.warning("Empty SQLite connection string; using default '%s'", conn_string)

        logger.info("Using SQLite checkpoint saver: %s", conn_string)
        return SqliteSaver.from_conn_string(conn_string)
    except ImportError:
        logger.exception("SQLite checkpoint saver not available; falling back to memory")
        return MemorySaver()
    except Exception:
        logger.exception("Failed to create SQLite checkpoint saver; falling back to memory")
        return MemorySaver()


def _create_postgres_saver(**kwargs: Any) -> BaseCheckpointSaver:
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        conn_string = kwargs.get("conn_string", "")
        if not conn_string:
            logger.error("PostgreSQL checkpoint saver requires a non-empty conn_string")
            raise ValueError("conn_string is required for PostgreSQL checkpoint saver")

        logger.info("Using PostgreSQL checkpoint saver")
        return PostgresSaver.from_conn_string(conn_string)
    except ImportError:
        logger.exception("PostgreSQL checkpoint saver not available; falling back to memory")
        return MemorySaver()
    except Exception:
        logger.exception("Failed to create PostgreSQL checkpoint saver; falling back to memory")
        return MemorySaver()
