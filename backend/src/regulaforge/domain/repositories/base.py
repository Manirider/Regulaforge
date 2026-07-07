"""Abstract repository interfaces (backward-compatible re-exports).

Repository abstractions are now defined in application/ports/repository.py
to comply with Clean Architecture (domain layer should not depend on
persistence/infrastructure patterns).

This module re-exports from the canonical location for backward
compatibility. New code should import directly from
regulaforge.application.ports.repository.
"""

from regulaforge.application.ports.repository import (
    BaseRepository,
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
    SearchableRepository,
)

# Backward-compatible alias: existing code imports Repository from here
Repository = BaseRepository

__all__ = [
    "BaseRepository",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "Repository",
    "RepositoryError",
    "SearchableRepository",
]
